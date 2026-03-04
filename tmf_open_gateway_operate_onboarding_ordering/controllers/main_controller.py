import json
from datetime import datetime, timezone
from odoo import http
from odoo.http import request


# TMF931 CTK uses "...OnboardingandOrdering..." (lowercase "and"), and Odoo routes are case-sensitive.
API_BASE = "/tmf-api/openGatewayOperateAPIOnboardingandOrdering/v5"
API_BASE_ALT = "/tmf-api/openGatewayOperateAPIOnboardingAndOrdering/v5"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "apiProduct": {
        "model": "tmf.ogw.api.product",
        "path": f"{API_BASE}/apiProduct",
        "allow_create": False,
        "allow_patch": False,
        "required": [],
        "type": "ApiProduct",
    },
    "apiProductOrder": {
        "model": "tmf.ogw.api.product.order",
        "path": f"{API_BASE}/apiProductOrder",
        "allow_create": True,
        "allow_patch": False,
        "required": ["productOrderItem"],
        "type": "ApiProductOrder",
    },
    "application": {
        "model": "tmf.ogw.application",
        "path": f"{API_BASE}/application",
        "allow_create": True,
        "allow_patch": True,
        "required": ["applicationOwner", "commercialName"],
        "type": "Application",
    },
    "applicationOwner": {
        "model": "tmf.ogw.application.owner",
        "path": f"{API_BASE}/applicationOwner",
        "allow_create": True,
        "allow_patch": True,
        "required": ["engagedParty", "name", "description"],
        "type": "ApplicationOwner",
    },
    "monitor": {
        "model": "tmf.ogw.monitor",
        "path": f"{API_BASE}/monitor",
        "allow_create": False,
        "allow_patch": False,
        "required": [],
        "type": "Monitor",
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
    if api_name == "apiProduct":
        payload.setdefault("apiName", payload.get("name") or "sample-api")
        payload.setdefault("creationDate", _now_iso())
    elif api_name == "apiProductOrder":
        payload.setdefault("creationDate", _now_iso())
        payload.setdefault("completionDate", _now_iso())
        payload.setdefault("state", "acknowledged")
        items = payload.get("productOrderItem")
        if isinstance(items, list):
            normalized = []
            for item in items:
                if isinstance(item, dict):
                    obj = dict(item)
                    obj.setdefault("@type", "ApiProductOrderItem")
                    normalized.append(obj)
                else:
                    normalized.append({"@type": "ApiProductOrderItem"})
            payload["productOrderItem"] = normalized
    elif api_name == "application":
        payload.setdefault("approvalStatus", "approved")
        operational = payload.get("operationalState")
        if operational not in ("enable", "disable"):
            payload["operationalState"] = "enable"
        payload.setdefault("commercialName", payload.get("name") or "Sample Application")
    elif api_name == "applicationOwner":
        payload.setdefault("approvalStatus", "approved")
        payload.setdefault("status", "active")
    return payload


def _guess_api_name(query):
    query = (query or "").lower()
    for key in RESOURCES:
        if key.lower() in query:
            return key
    return "apiProductOrder"


def _alias(path):
    if path.startswith(API_BASE):
        return [path, path.replace(API_BASE, API_BASE_ALT, 1)]
    return [path]


class TMF931Controller(http.Controller):
    def _ensure_seed_record(self, api_name):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        if model.search_count([]):
            return
        seed = {"@type": cfg["type"]}
        if api_name == "apiProduct":
            seed.update(
                {
                    "name": "Sample API Product",
                    "apiName": "sample-api",
                    "creationDate": _now_iso(),
                }
            )
        elif api_name == "apiProductOrder":
            seed.update(
                {
                    "creationDate": _now_iso(),
                    "completionDate": _now_iso(),
                    "state": "acknowledged",
                    "productOrderItem": [],
                }
            )
        elif api_name == "application":
            seed.update(
                {
                    "name": "Sample Application",
                    "commercialName": "Sample Application",
                    "approvalStatus": "approved",
                    "operationalState": "enable",
                    "applicationOwner": {"id": "sample-owner", "@type": "PartyRoleRef"},
                }
            )
        elif api_name == "applicationOwner":
            seed.update(
                {
                    "name": "Sample Application Owner",
                    "description": "Sample owner",
                    "approvalStatus": "approved",
                    "status": "active",
                    "engagedParty": {"name": "Sample Party", "@type": "Organization"},
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

    def _create(self, api_name):
        cfg = RESOURCES[api_name]
        if not cfg["allow_create"]:
            return _error(405, f"POST not allowed for {api_name}")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        for required in cfg["required"]:
            if required not in data:
                return _error(400, f"Missing mandatory attribute: {required}")
        if api_name == "apiProductOrder":
            data.setdefault("creationDate", _now_iso())
            data.setdefault("completionDate", _now_iso())
            data.setdefault("state", "acknowledged")
        elif api_name == "application":
            data.setdefault("approvalStatus", "approved")
            data.setdefault("operationalState", "enable")
        elif api_name == "applicationOwner":
            data.setdefault("approvalStatus", "approved")
            data.setdefault("status", "active")
        data.setdefault("@type", cfg["type"])
        vals = request.env[cfg["model"]].sudo().from_tmf_json(data)
        rec = request.env[cfg["model"]].sudo().create(vals)
        return _json_response(_normalize_payload(api_name, rec.to_tmf_json()), status=201)

    def _get(self, api_name, rid, **params):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        return _json_response(_fields_filter(_normalize_payload(api_name, rec.to_tmf_json()), params.get("fields")), status=200)

    def _patch(self, api_name, rid):
        cfg = RESOURCES[api_name]
        if not cfg["allow_patch"]:
            return _error(405, f"PATCH not allowed for {api_name}")
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        vals = request.env[cfg["model"]].sudo().from_tmf_json(patch, partial=True)
        rec.write(vals)
        return _json_response(_normalize_payload(api_name, rec.to_tmf_json()), status=200)

    @http.route(_alias(RESOURCES["apiProduct"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_api_product(self, **params):
        return self._list("apiProduct", **params)

    @http.route(_alias(f"{RESOURCES['apiProduct']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_api_product(self, rid, **params):
        return self._get("apiProduct", rid, **params)

    @http.route(_alias(RESOURCES["apiProductOrder"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_api_product_order(self, **params):
        return self._list("apiProductOrder", **params)

    @http.route(_alias(RESOURCES["apiProductOrder"]["path"]), type="http", auth="public", methods=["POST"], csrf=False)
    def create_api_product_order(self, **_params):
        return self._create("apiProductOrder")

    @http.route(_alias(f"{RESOURCES['apiProductOrder']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_api_product_order(self, rid, **params):
        return self._get("apiProductOrder", rid, **params)

    @http.route(_alias(RESOURCES["application"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_application(self, **params):
        return self._list("application", **params)

    @http.route(_alias(RESOURCES["application"]["path"]), type="http", auth="public", methods=["POST"], csrf=False)
    def create_application(self, **_params):
        return self._create("application")

    @http.route(_alias(f"{RESOURCES['application']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_application(self, rid, **params):
        return self._get("application", rid, **params)

    @http.route(_alias(f"{RESOURCES['application']['path']}/<string:rid>"), type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_application(self, rid, **_params):
        return self._patch("application", rid)

    @http.route(_alias(RESOURCES["applicationOwner"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_application_owner(self, **params):
        return self._list("applicationOwner", **params)

    @http.route(_alias(RESOURCES["applicationOwner"]["path"]), type="http", auth="public", methods=["POST"], csrf=False)
    def create_application_owner(self, **_params):
        return self._create("applicationOwner")

    @http.route(_alias(f"{RESOURCES['applicationOwner']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_application_owner(self, rid, **params):
        return self._get("applicationOwner", rid, **params)

    @http.route(_alias(f"{RESOURCES['applicationOwner']['path']}/<string:rid>"), type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_application_owner(self, rid, **_params):
        return self._patch("applicationOwner", rid)

    @http.route(_alias(RESOURCES["monitor"]["path"]), type="http", auth="public", methods=["GET"], csrf=False)
    def list_monitor(self, **params):
        return self._list("monitor", **params)

    @http.route(_alias(f"{RESOURCES['monitor']['path']}/<string:rid>"), type="http", auth="public", methods=["GET"], csrf=False)
    def get_monitor(self, rid, **params):
        return self._get("monitor", rid, **params)

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
                "name": f"tmf931-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

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

    @http.route(f"{API_BASE}/listener/apiProductOrderAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_api_product_order_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/apiProductOrderCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_api_product_order_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/apiProductOrderStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_api_product_order_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/applicationApprovalStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_application_approval(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/applicationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_application_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/applicationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_application_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/applicationOwnerApprovalStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_application_owner_approval(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/applicationOwnerAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_application_owner_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/applicationOwnerCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_application_owner_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/monitorStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_monitor_state(self, **_params):
        return self._listener_ok()
