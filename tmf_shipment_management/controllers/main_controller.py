import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/shipmentManagement/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "shipment": {
        "model": "tmf.shipment",
        "path": f"{API_BASE}/shipment",
        "alt_path": f"{API_BASE}/Shipment",
        "required": [],
    },
    "shipmentSpecification": {
        "model": "tmf.shipment.specification",
        "path": f"{API_BASE}/shipmentSpecification",
        "alt_path": f"{API_BASE}/ShipmentSpecification",
        "required": ["name"],
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


def _guess_api_name(query):
    q = (query or "").lower()
    if "shipmentspecification" in q:
        return "shipmentSpecification"
    return "shipment"


class TMF711Controller(http.Controller):
    def _list(self, api_name, **params):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        if params.get("description"):
            domain.append(("description", "=", params["description"]))
        if params.get("version"):
            domain.append(("version", "=", params["version"]))
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
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
        vals = request.env[cfg["model"]].sudo().from_tmf_json(patch, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    def _delete(self, api_name, rid):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route([RESOURCES["shipment"]["path"], RESOURCES["shipment"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_shipment(self, **params):
        return self._list("shipment", **params)

    @http.route([RESOURCES["shipment"]["path"], RESOURCES["shipment"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_shipment(self, **_params):
        return self._create("shipment")

    @http.route([f"{RESOURCES['shipment']['path']}/<string:rid>", f"{RESOURCES['shipment']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_shipment(self, rid, **params):
        return self._get("shipment", rid, **params)

    @http.route([f"{RESOURCES['shipment']['path']}/<string:rid>", f"{RESOURCES['shipment']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_shipment(self, rid, **_params):
        return self._patch("shipment", rid)

    @http.route([f"{RESOURCES['shipment']['path']}/<string:rid>", f"{RESOURCES['shipment']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_shipment(self, rid, **_params):
        return self._delete("shipment", rid)

    @http.route([RESOURCES["shipmentSpecification"]["path"], RESOURCES["shipmentSpecification"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_shipment_specification(self, **params):
        return self._list("shipmentSpecification", **params)

    @http.route([RESOURCES["shipmentSpecification"]["path"], RESOURCES["shipmentSpecification"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_shipment_specification(self, **_params):
        return self._create("shipmentSpecification")

    @http.route([f"{RESOURCES['shipmentSpecification']['path']}/<string:rid>", f"{RESOURCES['shipmentSpecification']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_shipment_specification(self, rid, **params):
        return self._get("shipmentSpecification", rid, **params)

    @http.route([f"{RESOURCES['shipmentSpecification']['path']}/<string:rid>", f"{RESOURCES['shipmentSpecification']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_shipment_specification(self, rid, **_params):
        return self._patch("shipmentSpecification", rid)

    @http.route([f"{RESOURCES['shipmentSpecification']['path']}/<string:rid>", f"{RESOURCES['shipmentSpecification']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_shipment_specification(self, rid, **_params):
        return self._delete("shipmentSpecification", rid)

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
                "name": f"tmf711-{api_name}-{callback}",
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
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/shipmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_spec_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_spec_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_spec_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shipmentSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipment_spec_delete(self, **_params):
        return self._listener_ok()
