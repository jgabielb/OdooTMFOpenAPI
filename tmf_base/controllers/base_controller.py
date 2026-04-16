# tmf_base/controllers/base_controller.py
import json
import logging
import time
import uuid
from urllib.parse import unquote

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TMFBaseController(http.Controller):
    """
    Shared helpers for all TMF API controllers.

    Subclass this instead of http.Controller to get:
    - Unified JSON response / error builders
    - Consistent field filtering ('?fields=...')
    - TMF ID normalisation
    - Pagination with X-Total-Count / X-Result-Count headers
    - Safe record lookup (tmf_id → numeric id fallback)
    """

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _get_correlation_id(self):
        """Return a correlation id for the current request.

        Priority:
        - X-Correlation-ID (preferred)
        - X-Request-ID
        - generated UUID4

        Stored on the request object to keep it stable during the request.
        """
        cid = getattr(request, "tmf_correlation_id", None)
        if cid:
            return cid

        headers = getattr(request, "httprequest", None) and request.httprequest.headers or {}
        cid = (headers.get("X-Correlation-ID") or headers.get("X-Request-ID") or "").strip()
        if not cid:
            cid = str(uuid.uuid4())

        request.tmf_correlation_id = cid
        return cid

    def _response_headers(self, headers=None):
        """Merge standard TMF API headers with custom headers."""
        h = list(headers or [])
        # Always return JSON from this helper.
        h.append(("Content-Type", "application/json"))
        # Correlation id for tracing across services.
        h.append(("X-Correlation-ID", self._get_correlation_id()))
        return h

    def _log_request(self, status, extra=None, level="info"):
        """Lightweight structured-ish request log."""
        req = request.httprequest
        payload = {
            "cid": self._get_correlation_id(),
            "method": getattr(req, "method", ""),
            "path": getattr(req, "path", ""),
            "query": getattr(req, "query_string", b"").decode("utf-8", errors="ignore"),
            "status": status,
        }
        if extra:
            payload.update(extra)

        log_fn = getattr(_logger, level, _logger.info)
        log_fn("TMF API %s", payload)

    def _json(self, payload, status=200, headers=None):
        """Return a JSON HTTP response with correct Content-Type."""
        h = self._response_headers(headers)
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=h,
        )

    def _error(self, status, reason, message):
        """Return a TMF-compliant error response."""
        # Always log errors with correlation id for traceability.
        self._log_request(status=status, extra={"reason": reason, "message": message}, level="warning")
        return self._json(
            {"code": str(status), "reason": reason, "message": message},
            status=status,
        )

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    def _parse_json_body(self):
        """Parse the request body as JSON, returning {} on empty body."""
        raw = request.httprequest.get_data(cache=False, as_text=False) or b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            if raw.strip() in (b"", b"{}"):
                return {}
            raise

    # ------------------------------------------------------------------
    # Field filtering
    # ------------------------------------------------------------------

    def _select_fields(self, obj, fields_param):
        """
        Apply the TMF 'fields' query param to a dict.

        Always preserves 'id', 'href', '@type' as required by TMF spec,
        even when they are not explicitly requested.
        """
        if not fields_param:
            return obj
        wanted = {f.strip() for f in fields_param.split(",") if f.strip()}
        if not wanted:
            return obj
        # Mandatory fields per TMF spec
        wanted |= {"id", "href", "@type"}
        return {k: v for k, v in obj.items() if k in wanted}

    def _select_fields_list(self, items, fields_param):
        """Apply _select_fields to every item in a list."""
        if not fields_param:
            return items
        return [self._select_fields(item, fields_param) for item in items]

    # ------------------------------------------------------------------
    # ID normalisation
    # ------------------------------------------------------------------

    def _normalize_tmf_id(self, tmf_id):
        """
        URL-decode a TMF ID and strip surrounding quotes that some CTK
        versions include in path segments.
        """
        value = unquote((tmf_id or "").strip())
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1].strip()
        return value

    # ------------------------------------------------------------------
    # Record lookup
    # ------------------------------------------------------------------

    def _find_record(self, model, tmf_id):
        """
        Look up a record by tmf_id, with a fallback to numeric DB id.

        Returns an empty recordset (falsy) when nothing is found.
        """
        env = request.env[model].sudo()
        rec = env.search([("tmf_id", "=", tmf_id)], limit=1)
        if rec:
            return rec
        if tmf_id.isdigit():
            rec = env.browse(int(tmf_id))
            if rec.exists():
                return rec
        return env  # empty recordset

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _paginate_params(self, kwargs):
        """
        Extract limit and offset from request kwargs with sane defaults/caps.

        Returns (limit, offset).
        """
        try:
            limit = max(1, min(int(kwargs.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(kwargs.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        return limit, offset

    def _list_response(self, model, domain, to_json_fn, kwargs, order="id asc"):
        """
        Search *model* with limit/offset from *kwargs*, serialise each record
        with *to_json_fn*, apply field filtering, and return a JSON response
        with X-Total-Count and X-Result-Count headers.

        Usage in a list route::

            @http.route(BASE, type='http', auth='public', methods=['GET'], csrf=False)
            def list_things(self, **kwargs):
                domain = self._build_domain(kwargs)
                return self._list_response(
                    'my.model', domain, lambda r: r.to_tmf_json(), kwargs
                )
        """
        start = time.perf_counter()
        limit, offset = self._paginate_params(kwargs)
        fields_param = kwargs.get("fields")

        env = request.env[model].sudo()
        records = env.search(domain, limit=limit, offset=offset, order=order)
        total = env.search_count(domain)

        data = self._select_fields_list(
            [to_json_fn(r) for r in records],
            fields_param,
        )

        headers = [
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(data))),
        ]
        resp = self._json(data, headers=headers)
        self._log_request(
            status=200,
            extra={
                "model": model,
                "limit": limit,
                "offset": offset,
                "total": total,
                "results": len(data),
                "ms": int((time.perf_counter() - start) * 1000),
            },
        )
        return resp

    # ------------------------------------------------------------------
    # Generic CRUD (used by migrated non-CTK controllers)
    # ------------------------------------------------------------------

    NON_PATCHABLE = {"id", "href"}

    def _tmf_do_list(self, cfg, **kw):
        return self._list_response(cfg["model"], [], lambda r: r.to_tmf_json(), kw)

    def _tmf_do_create(self, cfg):
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid JSON body")
        for req in cfg.get("required", []):
            if req not in data:
                return self._error(400, "Bad Request", f"Missing mandatory attribute: {req}")
        Model = request.env[cfg["model"]].sudo()
        if hasattr(Model, "from_tmf_json"):
            vals = Model.from_tmf_json(data)
        else:
            vals = data
        rec = Model.create(vals)
        return self._json(rec.to_tmf_json(), status=201)

    def _tmf_do_individual(self, cfg, rid, **kw):
        rid = self._normalize_tmf_id(rid)
        rec = self._find_record(cfg["model"], rid)
        if not rec:
            return self._error(404, "Not Found", f"{rid} not found")
        method = request.httprequest.method
        if method == "GET":
            return self._json(self._select_fields(rec.to_tmf_json(), kw.get("fields")))
        elif method == "PATCH":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            illegal = [k for k in data if k in self.NON_PATCHABLE]
            if illegal:
                return self._error(400, "Bad Request", f"Non-patchable attribute(s): {', '.join(illegal)}")
            Model = request.env[cfg["model"]].sudo()
            if hasattr(Model, "from_tmf_json"):
                vals = Model.from_tmf_json(data, partial=True)
            else:
                vals = data
            rec.write(vals)
            return self._json(rec.to_tmf_json())
        elif method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._error(405, "Method Not Allowed", f"{method} not supported")
