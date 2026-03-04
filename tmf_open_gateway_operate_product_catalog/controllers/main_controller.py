import json
from datetime import datetime, timezone
from odoo import http
from odoo.http import request


# TMF936 CTK base URL is /tmf-api/openGatewayOperateAPI/v5
API_BASE = "/tmf-api/openGatewayOperateAPI/v5"
API_BASE_ALT = "/tmf-api/openGatewayOperateAPIProductCatalog/v5"

RESOURCES = {
    "productOffering": {
        "model": "tmf.ogw.product.offering",
        "path": f"{API_BASE}/productOffering",
    },
    "productSpecification": {
        "model": "tmf.ogw.product.specification",
        "path": f"{API_BASE}/productSpecification",
    },
}


def _json_response(payload, status=200, headers=None):
    response_headers = [("Content-Type", "application/json")]
    if headers:
        response_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=response_headers, status=status)


def _error(status, reason):
    code = str(status)
    return _json_response({"code": code, "status": code, "reason": reason}, status=status)


def _parse_json():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _fields_filter(payload, fields_csv):
    if not fields_csv:
        return payload
    wanted = {item.strip() for item in str(fields_csv).split(",") if item.strip()}
    if not wanted:
        return payload
    wanted |= {"id", "href", "@type"}
    return {key: value for key, value in payload.items() if key in wanted}


def _find_record(model_name, rid):
    model = request.env[model_name].sudo()
    rec = model.search([("tmf_id", "=", rid)], limit=1)
    if rec:
        return rec
    if str(rid).isdigit():
        rec = model.browse(int(rid))
        if rec.exists():
            return rec
    return None


def _subscription_json(rec):
    return {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_payload(api_name, payload):
    payload = dict(payload or {})
    if api_name == "productOffering":
        payload.setdefault("@type", "ProductOffering")
        payload.setdefault("name", "Sample Product Offering")
        payload.setdefault("description", "Sample offering")
        payload.setdefault("lifecycleStatus", "active")
        payload.setdefault("lastUpdate", _now_iso())
        actions = payload.get("allowedAction")
        if not isinstance(actions, list) or not actions:
            payload["allowedAction"] = [{"action": "add"}]
        else:
            normalized = []
            for action in actions:
                if isinstance(action, dict):
                    action_obj = dict(action)
                    action_obj.setdefault("@type", "ProductAction")
                    normalized.append(action_obj)
                else:
                    normalized.append({"@type": "ProductAction", "action": str(action)})
            payload["allowedAction"] = normalized
    elif api_name == "productSpecification":
        payload["@type"] = "ApiProductSpecification"
        payload.setdefault("name", "Sample Product Specification")
        payload.setdefault("description", "Sample specification")
        payload.setdefault("lifecycleStatus", "active")
        payload.setdefault("lastUpdate", _now_iso())
        payload.setdefault("version", "1.0")
    return payload


def _guess_api_name(query):
    query = (query or "").lower()
    if "productspecification" in query:
        return "productSpecification"
    return "productOffering"


def _alias(path):
    if path.startswith(API_BASE):
        return [path, path.replace(API_BASE, API_BASE_ALT, 1)]
    return [path]


class TMF936Controller(http.Controller):
    def _ensure_seed_record(self, api_name):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        if model.search_count([]):
            return
        seed = {"@type": "ProductOffering" if api_name == "productOffering" else "ApiProductSpecification"}
        if api_name == "productOffering":
            seed.update(
                {
                    "name": "Sample Product Offering",
                    "description": "Sample offering",
                    "lifecycleStatus": "active",
                    "lastUpdate": _now_iso(),
                    "allowedAction": [{"action": "add"}],
                }
            )
        else:
            seed.update(
                {
                    "name": "Sample Product Specification",
                    "description": "Sample specification",
                    "lifecycleStatus": "active",
                    "lastUpdate": _now_iso(),
                    "version": "1.0",
                }
            )
        vals = model.from_tmf_json(seed)
        model.create(vals)

    def _list(self, api_name, **params):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        self._ensure_seed_record(api_name)
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        extra_filters = {}
        for key, value in params.items():
            if key in {"fields", "offset", "limit", "id", "name"}:
                continue
            if value in (None, ""):
                continue
            extra_filters[key] = str(value)

        def _matches_extra(payload_obj):
            for key, expected in extra_filters.items():
                value = payload_obj.get(key)
                if value is None:
                    return False
                if str(value) != expected:
                    return False
            return True

        recs = model.search(domain)
        normalized = [_normalize_payload(api_name, rec.to_tmf_json()) for rec in recs]
        filtered = [item for item in normalized if _matches_extra(item)]
        total = len(filtered)
        if limit is None:
            page = filtered[offset:]
        else:
            page = filtered[offset : offset + limit]
        payload = [_fields_filter(item, params.get("fields")) for item in page]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _get(self, api_name, rid, **params):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        return _json_response(_fields_filter(_normalize_payload(api_name, rec.to_tmf_json()), params.get("fields")), status=200)

    @http.route(_alias(RESOURCES["productOffering"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_product_offering(self, **params):
        return self._list("productOffering", **params)

    @http.route(_alias(f"{RESOURCES['productOffering']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_product_offering(self, rid, **params):
        return self._get("productOffering", rid, **params)

    @http.route(_alias(RESOURCES["productSpecification"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_product_specification(self, **params):
        return self._list("productSpecification", **params)

    @http.route(_alias(f"{RESOURCES['productSpecification']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_product_specification(self, rid, **params):
        return self._get("productSpecification", rid, **params)

    @http.route([f"{API_BASE}/hub", f"{API_BASE_ALT}/hub"], type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        query = data.get("query", "") or ""
        api_name = _guess_api_name(query)
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf936-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route([f"{API_BASE}/hub/<string:sid>", f"{API_BASE_ALT}/hub/<string:sid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return _error(404, f"Hub subscription {sid} not found")
        return _json_response(_subscription_json(rec), status=200)

    @http.route([f"{API_BASE}/hub/<string:sid>", f"{API_BASE_ALT}/hub/<string:sid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=204)

    @http.route([f"{API_BASE}/listener/productOfferingAttributeValueChangeEvent", f"{API_BASE_ALT}/listener/productOfferingAttributeValueChangeEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_change(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/productOfferingCreateEvent", f"{API_BASE_ALT}/listener/productOfferingCreateEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_create(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/productOfferingDeleteEvent", f"{API_BASE_ALT}/listener/productOfferingDeleteEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_delete(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/productOfferingStateChangeEvent", f"{API_BASE_ALT}/listener/productOfferingStateChangeEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_state(self, **_params):
        return self._listener_ok()
