import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/resourceFunctionActivation/v4"
BASE_PATH = f"{API_BASE}/resourceFunction"
NON_PATCHABLE = {"id", "href", "usageState"}


def _json_response(payload, status=200, headers=None):
    response_headers = [("Content-Type", "application/json")]
    if headers:
        response_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=response_headers, status=status)


def _tmf_error(status, reason):
    status_str = str(status)
    return _json_response({"code": status_str, "status": status_str, "reason": reason}, status=status)


def _parse_body():
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
    wanted |= {"id", "href"}
    return {key: value for key, value in payload.items() if key in wanted}


def _find_by_id(rid):
    model = request.env["tmf.resource.function"].sudo()
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


class TMF664Controller(http.Controller):
    @http.route(BASE_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_resource_functions(self, **params):
        model = request.env["tmf.resource.function"].sudo()
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        total = model.search_count([])
        recs = model.search([], offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource_function(self, rid, **params):
        rec = _find_by_id(rid)
        if not rec:
            return _tmf_error(404, f"ResourceFunction {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(BASE_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_resource_function(self, **_params):
        data = _parse_body()
        if not isinstance(data, dict):
            return _tmf_error(400, "Invalid JSON body")
        try:
            vals = request.env["tmf.resource.function"].sudo().from_tmf_json(data)
            rec = request.env["tmf.resource.function"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)
        except Exception as exc:
            return _tmf_error(400, f"Create failed: {exc}")

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_resource_function(self, rid, **_params):
        rec = _find_by_id(rid)
        if not rec:
            return _tmf_error(404, f"ResourceFunction {rid} not found")
        patch = _parse_body()
        if not isinstance(patch, dict):
            return _tmf_error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _tmf_error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        try:
            vals = request.env["tmf.resource.function"].sudo().from_tmf_json(patch, partial=True)
            rec.write(vals)
            return _json_response(rec.to_tmf_json(), status=200)
        except Exception as exc:
            return _tmf_error(400, f"Patch failed: {exc}")

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_resource_function(self, rid, **_params):
        rec = _find_by_id(rid)
        if not rec:
            return _tmf_error(404, f"ResourceFunction {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_body()
        if not isinstance(data, dict):
            return _tmf_error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _tmf_error(400, "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf664-resourceFunction-{callback}",
                "api_name": "resourceFunction",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "resourceFunction":
            return _tmf_error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_body()
        if not isinstance(data, dict):
            return _tmf_error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/resourceFunctionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_resource_function_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/resourceFunctionAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_resource_function_attribute_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/resourceFunctionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_resource_function_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/resourceFunctionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_resource_function_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/monitorCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_monitor_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/monitorAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_monitor_attribute_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/monitorStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_monitor_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/monitorDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_monitor_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/healCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_heal_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/healAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_heal_attribute_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/healStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_heal_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/healDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_heal_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/scaleCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_scale_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/scaleAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_scale_attribute_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/scaleStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_scale_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/scaleDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_scale_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/migrateCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_migrate_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/migrateAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_migrate_attribute_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/migrateStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_migrate_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/migrateDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_migrate_delete(self, **_params):
        return self._listener_ok()
