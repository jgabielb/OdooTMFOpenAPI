# tmf_base/controllers/base_controller.py
import json
import logging
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

    def _json(self, payload, status=200, headers=None):
        """Return a JSON HTTP response with correct Content-Type."""
        h = list(headers or []) + [('Content-Type', 'application/json')]
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=h,
        )

    def _error(self, status, reason, message):
        """Return a TMF-compliant error response."""
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
        return self._json(data, headers=headers)
