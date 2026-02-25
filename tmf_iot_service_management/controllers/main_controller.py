import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/iotservicemanagement/v4"
RESOURCE_MODEL = "tmf.iot.service.resource"
NON_PATCHABLE = {"id", "href"}
RESOURCES = set(('iotService','serviceCatalog','serviceCategory','serviceCandidate','serviceQualification','serviceProblem','iotServiceSpecification','serviceTest','serviceTestSpecification','usageConsumptionReportRequest','user','usageConsumptionReport','importJob','exportJob'))
LISTENER_EVENTS = set(('iotServiceCreateEvent','iotServiceAttributeValueChangeEvent','iotServiceStateChangeEvent','iotServiceBatchEvent','iotServiceDeleteEvent'))


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


def _find_record(resource, rid):
    model = request.env[RESOURCE_MODEL].sudo()
    rec = model.search([("resource_type", "=", resource), ("tmf_id", "=", rid)], limit=1)
    if rec:
        return rec
    if str(rid).isdigit():
        rec = model.browse(int(rid))
        if rec.exists() and rec.resource_type == resource:
            return rec
    return None


def _subscription_json(rec):
    return {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}


class TMFController(http.Controller):
    @http.route(API_BASE + "/<string:resource>", type="http", auth="public", methods=["GET"], csrf=False)
    def list_resource(self, resource, **params):
        if resource not in RESOURCES:
            return _error(404, f"Resource {resource} not found")
        model = request.env[RESOURCE_MODEL].sudo()
        domain = [("resource_type", "=", resource)]
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

    @http.route(API_BASE + "/<string:resource>", type="http", auth="public", methods=["POST"], csrf=False)
    def create_resource(self, resource, **_params):
        if resource not in RESOURCES:
            return _error(404, f"Resource {resource} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        data.setdefault("@type", resource[:1].upper() + resource[1:])
        vals = request.env[RESOURCE_MODEL].sudo().from_tmf_json(data, resource_type=resource)
        rec = request.env[RESOURCE_MODEL].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(API_BASE + "/<string:resource>/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource(self, resource, rid, **params):
        if resource not in RESOURCES:
            return _error(404, f"Resource {resource} not found")
        rec = _find_record(resource, rid)
        if not rec:
            return _error(404, f"{resource} {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(API_BASE + "/<string:resource>/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_resource(self, resource, rid, **_params):
        if resource not in RESOURCES:
            return _error(404, f"Resource {resource} not found")
        rec = _find_record(resource, rid)
        if not rec:
            return _error(404, f"{resource} {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        vals = request.env[RESOURCE_MODEL].sudo().from_tmf_json(patch, resource_type=resource, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(API_BASE + "/<string:resource>/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_resource(self, resource, rid, **_params):
        if resource not in RESOURCES:
            return _error(404, f"Resource {resource} not found")
        rec = _find_record(resource, rid)
        if not rec:
            return _error(404, f"{resource} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(API_BASE + "/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        query = data.get("query", "") or ""
        api_name = "iotService"
        for resource in RESOURCES:
            if resource.lower() in query.lower():
                api_name = resource
                break
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": "tmf_iot_service_management-" + api_name + "-" + callback,
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(API_BASE + "/hub/<string:sid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return _error(404, f"Hub subscription {sid} not found")
        return _json_response(_subscription_json(rec), status=200)

    @http.route(API_BASE + "/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(API_BASE + "/listener/<string:event_name>", type="http", auth="public", methods=["POST"], csrf=False)
    def listener(self, event_name, **_params):
        if LISTENER_EVENTS and event_name not in LISTENER_EVENTS:
            return _error(404, f"Listener {event_name} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=204)

    @http.route(API_BASE + "/openid/userinfo", type="http", auth="public", methods=["GET"], csrf=False)
    def openid_userinfo(self, **_params):
        if "tmf_iot_service_management" != "tmf_self_care_management":
            return _error(404, "Not found")
        payload = {
            "sub": "odoo-user",
            "name": "Odoo User",
            "preferred_username": "odoo",
        }
        return _json_response(payload, status=200)

