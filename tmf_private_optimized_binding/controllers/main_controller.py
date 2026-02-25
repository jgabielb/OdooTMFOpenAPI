import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/privateOptimizedBinding/v5"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "cloudApplication": {
        "model": "tmf.cloud.application",
        "path": f"{API_BASE}/cloudApplication",
        "required": ["operationalState", "@type"],
    },
    "cloudApplicationSpecification": {
        "model": "tmf.cloud.application.specification",
        "path": f"{API_BASE}/cloudApplicationSpecification",
        "required": ["@type"],
    },
    "userEquipment": {
        "model": "tmf.user.equipment",
        "path": f"{API_BASE}/userEquipment",
        "required": ["operationalState", "@type"],
    },
    "userEquipmentSpecification": {
        "model": "tmf.user.equipment.specification",
        "path": f"{API_BASE}/userEquipmentSpecification",
        "required": ["hasNetworkInterface", "isPortable", "isWearable", "@type"],
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


def _guess_api_name(query):
    query = (query or "").lower()
    if "cloudapplicationspecification" in query:
        return "cloudApplicationSpecification"
    if "userequipmentspecification" in query:
        return "userEquipmentSpecification"
    if "cloudapplication" in query:
        return "cloudApplication"
    return "userEquipment"


class TMF759Controller(http.Controller):
    def _list(self, api_name, **params):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _create(self, api_name):
        cfg = RESOURCES[api_name]
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        for required in cfg["required"]:
            if required not in data:
                return _error(400, f"Missing mandatory attribute: {required}")
        vals = request.env[cfg["model"]].sudo().from_tmf_json(data)
        rec = request.env[cfg["model"]].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    def _get(self, api_name, rid, **params):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    def _patch(self, api_name, rid):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        merged = rec.to_tmf_json()
        merged.update(patch)
        vals = request.env[cfg["model"]].sudo().from_tmf_json(merged, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    def _delete(self, api_name, rid):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route([RESOURCES["cloudApplication"]["path"], f"{API_BASE}/CloudApplication"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_cloud_application(self, **params):
        return self._list("cloudApplication", **params)

    @http.route([RESOURCES["cloudApplication"]["path"], f"{API_BASE}/CloudApplication"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_cloud_application(self, **_params):
        return self._create("cloudApplication")

    @http.route([f"{RESOURCES['cloudApplication']['path']}/<string:rid>", f"{API_BASE}/CloudApplication/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_cloud_application(self, rid, **params):
        return self._get("cloudApplication", rid, **params)

    @http.route([f"{RESOURCES['cloudApplication']['path']}/<string:rid>", f"{API_BASE}/CloudApplication/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_cloud_application(self, rid, **_params):
        return self._patch("cloudApplication", rid)

    @http.route([f"{RESOURCES['cloudApplication']['path']}/<string:rid>", f"{API_BASE}/CloudApplication/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_cloud_application(self, rid, **_params):
        return self._delete("cloudApplication", rid)

    @http.route([RESOURCES["cloudApplicationSpecification"]["path"], f"{API_BASE}/CloudApplicationSpecification"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_cloud_application_specification(self, **params):
        return self._list("cloudApplicationSpecification", **params)

    @http.route([RESOURCES["cloudApplicationSpecification"]["path"], f"{API_BASE}/CloudApplicationSpecification"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_cloud_application_specification(self, **_params):
        return self._create("cloudApplicationSpecification")

    @http.route([f"{RESOURCES['cloudApplicationSpecification']['path']}/<string:rid>", f"{API_BASE}/CloudApplicationSpecification/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_cloud_application_specification(self, rid, **params):
        return self._get("cloudApplicationSpecification", rid, **params)

    @http.route([f"{RESOURCES['cloudApplicationSpecification']['path']}/<string:rid>", f"{API_BASE}/CloudApplicationSpecification/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_cloud_application_specification(self, rid, **_params):
        return self._patch("cloudApplicationSpecification", rid)

    @http.route([f"{RESOURCES['cloudApplicationSpecification']['path']}/<string:rid>", f"{API_BASE}/CloudApplicationSpecification/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_cloud_application_specification(self, rid, **_params):
        return self._delete("cloudApplicationSpecification", rid)

    @http.route([RESOURCES["userEquipment"]["path"], f"{API_BASE}/UserEquipment"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_user_equipment(self, **params):
        return self._list("userEquipment", **params)

    @http.route([RESOURCES["userEquipment"]["path"], f"{API_BASE}/UserEquipment"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_user_equipment(self, **_params):
        return self._create("userEquipment")

    @http.route([f"{RESOURCES['userEquipment']['path']}/<string:rid>", f"{API_BASE}/UserEquipment/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_user_equipment(self, rid, **params):
        return self._get("userEquipment", rid, **params)

    @http.route([f"{RESOURCES['userEquipment']['path']}/<string:rid>", f"{API_BASE}/UserEquipment/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_user_equipment(self, rid, **_params):
        return self._patch("userEquipment", rid)

    @http.route([f"{RESOURCES['userEquipment']['path']}/<string:rid>", f"{API_BASE}/UserEquipment/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_user_equipment(self, rid, **_params):
        return self._delete("userEquipment", rid)

    @http.route([RESOURCES["userEquipmentSpecification"]["path"], f"{API_BASE}/UserEquipmentSpecification"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_user_equipment_specification(self, **params):
        return self._list("userEquipmentSpecification", **params)

    @http.route([RESOURCES["userEquipmentSpecification"]["path"], f"{API_BASE}/UserEquipmentSpecification"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_user_equipment_specification(self, **_params):
        return self._create("userEquipmentSpecification")

    @http.route([f"{RESOURCES['userEquipmentSpecification']['path']}/<string:rid>", f"{API_BASE}/UserEquipmentSpecification/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_user_equipment_specification(self, rid, **params):
        return self._get("userEquipmentSpecification", rid, **params)

    @http.route([f"{RESOURCES['userEquipmentSpecification']['path']}/<string:rid>", f"{API_BASE}/UserEquipmentSpecification/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_user_equipment_specification(self, rid, **_params):
        return self._patch("userEquipmentSpecification", rid)

    @http.route([f"{RESOURCES['userEquipmentSpecification']['path']}/<string:rid>", f"{API_BASE}/UserEquipmentSpecification/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_user_equipment_specification(self, rid, **_params):
        return self._delete("userEquipmentSpecification", rid)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
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
                "name": f"tmf759-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
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

    @http.route(f"{API_BASE}/listener/cloudApplicationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/cloudApplicationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/cloudApplicationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/cloudApplicationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/cloudApplicationSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_spec_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/cloudApplicationSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_spec_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/cloudApplicationSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cloud_application_spec_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_spec_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_spec_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/userEquipmentSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_user_equipment_spec_delete(self, **_params):
        return self._listener_ok()
