import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/entityInventory/v4"
ENTITY_PATH = f"{API_BASE}/entity"
ASSOCIATION_PATH = f"{API_BASE}/association"
NON_PATCHABLE = {"id", "href"}


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
    wanted = {part.strip() for part in str(fields_csv).split(",") if part.strip()}
    if not wanted:
        return payload
    wanted |= {"id", "href"}
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


class TMF703Controller(http.Controller):
    @http.route(ENTITY_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_entity(self, **params):
        model = request.env["tmf.entity"].sudo()
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        total = model.search_count([])
        recs = model.search([], offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(ENTITY_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_entity(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        if not data.get("@type"):
            return _error(400, "Missing mandatory attribute: @type")
        vals = request.env["tmf.entity"].sudo().from_tmf_json(data)
        rec = request.env["tmf.entity"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{ENTITY_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def retrieve_entity(self, rid, **params):
        rec = _find_record("tmf.entity", rid)
        if not rec:
            return _error(404, f"Entity {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{ENTITY_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_entity(self, rid, **_params):
        rec = _find_record("tmf.entity", rid)
        if not rec:
            return _error(404, f"Entity {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        vals = request.env["tmf.entity"].sudo().from_tmf_json(patch, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{ENTITY_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_entity(self, rid, **_params):
        rec = _find_record("tmf.entity", rid)
        if not rec:
            return _error(404, f"Entity {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(ASSOCIATION_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_association(self, **params):
        model = request.env["tmf.entity.association"].sudo()
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        total = model.search_count([])
        recs = model.search([], offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(ASSOCIATION_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_association(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        if not data.get("name"):
            return _error(400, "Missing mandatory attribute: name")
        if not data.get("associationRole"):
            return _error(400, "Missing mandatory attribute: associationRole")
        vals = request.env["tmf.entity.association"].sudo().from_tmf_json(data)
        rec = request.env["tmf.entity.association"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{ASSOCIATION_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def retrieve_association(self, rid, **params):
        rec = _find_record("tmf.entity.association", rid)
        if not rec:
            return _error(404, f"Association {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{ASSOCIATION_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_association(self, rid, **_params):
        rec = _find_record("tmf.entity.association", rid)
        if not rec:
            return _error(404, f"Association {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        vals = request.env["tmf.entity.association"].sudo().from_tmf_json(patch, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{ASSOCIATION_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_association(self, rid, **_params):
        rec = _find_record("tmf.entity.association", rid)
        if not rec:
            return _error(404, f"Association {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        query = data.get("query", "") or ""
        api_name = "association" if "Association" in query else "entity"
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf703-{api_name}-{callback}",
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
        if not rec or not rec.exists() or rec.api_name not in {"entity", "association"}:
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/entityCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_entity_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/entityChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_entity_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/entityDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_entity_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/associationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_association_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/associationChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_association_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/associationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_association_delete(self, **_params):
        return self._listener_ok()
