import json
import logging
import uuid
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/productConfigurationManagement/v5"
LEGACY_BASE = "/tmf-api/productManagement/v5"

RESOURCES = {
    "checkProductConfiguration": {
        "model": "tmf.check.product.configuration",
        "type": "CheckProductConfiguration",
        "item_key": "checkProductConfigurationItem",
        "item_type": "CheckProductConfigurationItem",
        "required": ["checkProductConfigurationItem"],
    },
    "queryProductConfiguration": {
        "model": "tmf.query.product.configuration",
        "type": "QueryProductConfiguration",
        "item_key": "requestProductConfigurationItem",
        "item_type": "QueryProductConfigurationItem",
        "required": ["requestProductConfigurationItem"],
    },
}


class TMF760ProductConfigurationController(http.Controller):
    def _json_response(self, payload, status=200, extra_headers=None):
        headers = [("Content-Type", "application/json")]
        if extra_headers:
            headers.extend(extra_headers)
        return request.make_response(json.dumps(payload), headers=headers, status=status)

    def _error(self, status, reason):
        code = str(status)
        return self._json_response({"code": code, "status": code, "reason": reason}, status=status)

    def _new_id(self):
        return str(uuid.uuid4())

    def _mk_href(self, resource, rid):
        return f"{API_BASE}/{resource}/{rid}"

    def _parse_json(self):
        try:
            return json.loads(request.httprequest.data or b"{}")
        except Exception:
            return None

    def _apply_fields_filter(self, obj, fields_param):
        if not fields_param or not isinstance(obj, dict):
            return obj
        keep = {f.strip() for f in str(fields_param).split(",") if f.strip()}
        keep |= {"id", "href", "@type"}
        return {k: v for k, v in obj.items() if k in keep}

    def _find_record(self, model_name, rid):
        model = request.env[model_name].sudo()
        rec = model.search([("tmf_id", "=", rid)], limit=1)
        if rec:
            return rec
        if str(rid).isdigit():
            rec = model.browse(int(rid))
            if rec.exists():
                return rec
        return None

    def _get_resource_json(self, rec, api_name):
        cfg = RESOURCES[api_name]
        obj = rec.resource_json or rec.response_payload or rec.request_payload or {}
        if not isinstance(obj, dict):
            obj = {}
        obj.setdefault("id", rec.tmf_id)
        obj.setdefault("href", rec.href)
        obj.setdefault("@type", cfg["type"])
        obj.setdefault("state", rec.state or "acknowledged")

        if api_name == "queryProductConfiguration" and "queryProductConfigurationItem" in obj and "requestProductConfigurationItem" not in obj:
            obj["requestProductConfigurationItem"] = obj.get("queryProductConfigurationItem") or []

        item_key = cfg["item_key"]
        obj.setdefault(item_key, obj.get(item_key) or [])
        if api_name == "queryProductConfiguration":
            obj.setdefault("computedProductConfigurationItem", obj.get("computedProductConfigurationItem") or [])
        return obj

    def _normalize_items(self, resource, item_key, item_type):
        for idx, item in enumerate(resource.get(item_key) or []):
            if isinstance(item, dict):
                item.setdefault("@type", item_type)
                item.setdefault("id", item.get("id") or f"{idx + 1:02d}")

    def _notify(self, api_name, action, resource_json):
        try:
            request.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=resource_json,
            )
        except Exception:
            pass

    def _list_with_pagination(self, api_name, fields_param):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        total = model.search_count([])

        try:
            offset = int(request.params.get("offset", 0))
        except Exception:
            offset = 0
        try:
            limit = int(request.params.get("limit", 0))
        except Exception:
            limit = 0

        recs = model.search([], offset=offset, limit=limit if limit > 0 else None)
        items = [self._apply_fields_filter(self._get_resource_json(rec, api_name), fields_param) for rec in recs]
        headers = [("X-Result-Count", str(len(items))), ("X-Total-Count", str(total))]
        return self._json_response(items, status=200, extra_headers=headers)

    def _create(self, api_name):
        cfg = RESOURCES[api_name]
        payload = self._parse_json()
        if not isinstance(payload, dict):
            return self._error(400, "Invalid JSON body")

        for required in cfg["required"]:
            if required not in payload:
                return self._error(400, f"Missing mandatory attribute: {required}")

        rid = self._new_id()
        href = self._mk_href(api_name, rid)
        resource = dict(payload)
        resource["id"] = rid
        resource["href"] = href
        resource["@type"] = resource.get("@type") or cfg["type"]
        resource["state"] = resource.get("state") or "acknowledged"

        if api_name == "queryProductConfiguration":
            # Legacy compatibility while producing spec-compliant field name.
            if "requestProductConfigurationItem" not in resource and "queryProductConfigurationItem" in resource:
                resource["requestProductConfigurationItem"] = resource.get("queryProductConfigurationItem") or []
            resource.setdefault("computedProductConfigurationItem", resource.get("computedProductConfigurationItem") or [])

        item_key = cfg["item_key"]
        resource.setdefault(item_key, resource.get(item_key) or [])
        self._normalize_items(resource, item_key, cfg["item_type"])
        if api_name == "queryProductConfiguration":
            self._normalize_items(resource, "computedProductConfigurationItem", cfg["item_type"])

        request.env[cfg["model"]].sudo().create(
            {
                "tmf_id": rid,
                "href": href,
                "state": resource["state"],
                "request_payload": payload,
                "response_payload": resource,
                "resource_json": resource,
            }
        )

        self._notify(api_name, "create", resource)
        self._notify(api_name, "state_change", resource)

        fields_param = request.params.get("fields")
        response_body = self._apply_fields_filter(resource, fields_param)
        location = request.httprequest.host_url.rstrip("/") + href
        # CTK expects 201 on POST for TMF760 resources.
        return self._json_response(response_body, status=201, extra_headers=[("Location", location)])

    def _get_by_id(self, api_name, rid):
        cfg = RESOURCES[api_name]
        rec = self._find_record(cfg["model"], rid)
        if not rec:
            return self._error(404, f"{cfg['type']} {rid} not found")
        fields_param = request.params.get("fields")
        return self._json_response(self._apply_fields_filter(self._get_resource_json(rec, api_name), fields_param), status=200)

    def _subscription_json(self, rec):
        return {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}

    def _guess_api_name(self, query):
        q = (query or "").lower()
        if "queryproductconfiguration" in q:
            return "queryProductConfiguration"
        return "checkProductConfiguration"

    def _listener_ok(self):
        payload = self._parse_json()
        if not isinstance(payload, dict):
            return self._error(400, "Invalid JSON body")
        return request.make_response("", status=204)

    # ---------------- CHECK PRODUCT CONFIGURATION ----------------

    @http.route([
        f"{API_BASE}/checkProductConfiguration",
        f"{API_BASE}/checkProductConfiguration/",
        f"{LEGACY_BASE}/checkProductConfiguration",
        f"{LEGACY_BASE}/checkProductConfiguration/",
    ], type="http", auth="public", methods=["POST"], csrf=False)
    def post_check_product_configuration(self, **_params):
        try:
            return self._create("checkProductConfiguration")
        except Exception as exc:
            _logger.exception("POST /checkProductConfiguration failed")
            return self._error(400, f"Create failed: {exc}")

    @http.route([
        f"{API_BASE}/checkProductConfiguration",
        f"{API_BASE}/checkProductConfiguration/",
        f"{LEGACY_BASE}/checkProductConfiguration",
        f"{LEGACY_BASE}/checkProductConfiguration/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_check_product_configuration(self, **_params):
        fields_param = request.params.get("fields")
        return self._list_with_pagination("checkProductConfiguration", fields_param)

    @http.route([
        f"{API_BASE}/checkProductConfiguration/<string:rid>",
        f"{API_BASE}/checkProductConfiguration/<string:rid>/",
        f"{LEGACY_BASE}/checkProductConfiguration/<string:rid>",
        f"{LEGACY_BASE}/checkProductConfiguration/<string:rid>/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_check_product_configuration_by_id(self, rid, **_params):
        return self._get_by_id("checkProductConfiguration", rid)

    # ---------------- QUERY PRODUCT CONFIGURATION ----------------

    @http.route([
        f"{API_BASE}/queryProductConfiguration",
        f"{API_BASE}/queryProductConfiguration/",
        f"{LEGACY_BASE}/queryProductConfiguration",
        f"{LEGACY_BASE}/queryProductConfiguration/",
    ], type="http", auth="public", methods=["POST"], csrf=False)
    def post_query_product_configuration(self, **_params):
        try:
            return self._create("queryProductConfiguration")
        except Exception as exc:
            _logger.exception("POST /queryProductConfiguration failed")
            return self._error(400, f"Create failed: {exc}")

    @http.route([
        f"{API_BASE}/queryProductConfiguration",
        f"{API_BASE}/queryProductConfiguration/",
        f"{LEGACY_BASE}/queryProductConfiguration",
        f"{LEGACY_BASE}/queryProductConfiguration/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_query_product_configuration(self, **_params):
        fields_param = request.params.get("fields")
        return self._list_with_pagination("queryProductConfiguration", fields_param)

    @http.route([
        f"{API_BASE}/queryProductConfiguration/<string:rid>",
        f"{API_BASE}/queryProductConfiguration/<string:rid>/",
        f"{LEGACY_BASE}/queryProductConfiguration/<string:rid>",
        f"{LEGACY_BASE}/queryProductConfiguration/<string:rid>/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_query_product_configuration_by_id(self, rid, **_params):
        return self._get_by_id("queryProductConfiguration", rid)

    # ---------------- HUB / LISTENERS ----------------

    @http.route([f"{API_BASE}/hub", f"{LEGACY_BASE}/hub"], type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = self._parse_json()
        if not isinstance(data, dict):
            return self._error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return self._error(400, "Missing mandatory attribute: callback")

        query = data.get("query", "") or ""
        api_name = self._guess_api_name(query)
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf760-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return self._json_response(self._subscription_json(rec), status=201)

    @http.route([f"{API_BASE}/hub/<string:sid>", f"{LEGACY_BASE}/hub/<string:sid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return self._error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route([f"{API_BASE}/listener/checkProductConfigurationCreateEvent", f"{LEGACY_BASE}/listener/checkProductConfigurationCreateEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_check_create(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/checkProductConfigurationAttributeValueChangeEvent", f"{LEGACY_BASE}/listener/checkProductConfigurationAttributeValueChangeEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_check_change(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/checkProductConfigurationStateChangeEvent", f"{LEGACY_BASE}/listener/checkProductConfigurationStateChangeEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_check_state(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/checkProductConfigurationDeleteEvent", f"{LEGACY_BASE}/listener/checkProductConfigurationDeleteEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_check_delete(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/queryProductConfigurationCreateEvent", f"{LEGACY_BASE}/listener/queryProductConfigurationCreateEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_query_create(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/queryProductConfigurationAttributeValueChangeEvent", f"{LEGACY_BASE}/listener/queryProductConfigurationAttributeValueChangeEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_query_change(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/queryProductConfigurationStateChangeEvent", f"{LEGACY_BASE}/listener/queryProductConfigurationStateChangeEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_query_state(self, **_params):
        return self._listener_ok()

    @http.route([f"{API_BASE}/listener/queryProductConfigurationDeleteEvent", f"{LEGACY_BASE}/listener/queryProductConfigurationDeleteEvent"], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_query_delete(self, **_params):
        return self._listener_ok()
