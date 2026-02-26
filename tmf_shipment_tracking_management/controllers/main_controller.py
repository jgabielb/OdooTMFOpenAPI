import json
from odoo import http
from odoo.http import request


API_BASES = [
    "/tmf-api/shipmentTracking/v4",
    "/tmf-api/shipmentTrackingManagement/v4",
]
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
    wanted = {item.strip() for item in str(fields_csv).split(",") if item.strip()}
    if not wanted:
        return payload
    wanted |= {"id", "href", "@type"}
    return {key: value for key, value in payload.items() if key in wanted}


def _find_record(rid):
    model = request.env["tmf.shipment.tracking"].sudo()
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


class TMF684Controller(http.Controller):
    def _list(self, **params):
        model = request.env["tmf.shipment.tracking"].sudo()
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("trackingNumber"):
            domain.append(("tracking_number", "=", params["trackingNumber"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _create(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        try:
            vals = request.env["tmf.shipment.tracking"].sudo().from_tmf_json(data)
            rec = request.env["tmf.shipment.tracking"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)
        except Exception as exc:
            return _error(500, f"Create shipmentTracking failed: {exc}")

    def _get(self, rid, **params):
        rec = _find_record(rid)
        if not rec:
            return _error(404, f"shipmentTracking {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    def _patch(self, rid):
        rec = _find_record(rid)
        if not rec:
            return _error(404, f"shipmentTracking {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        try:
            vals = request.env["tmf.shipment.tracking"].sudo().from_tmf_json(patch, partial=True)
            rec.write(vals)
            return _json_response(rec.to_tmf_json(), status=200)
        except Exception as exc:
            return _error(500, f"Patch shipmentTracking failed: {exc}")

    def _delete(self, rid):
        rec = _find_record(rid)
        if not rec:
            return _error(404, f"shipmentTracking {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route([f"{b}/shipmentTracking" for b in API_BASES], type="http", auth="public", methods=["GET"], csrf=False)
    def list_shipment_tracking(self, **params):
        return self._list(**params)

    @http.route([f"{b}/shipmentTracking" for b in API_BASES], type="http", auth="public", methods=["POST"], csrf=False)
    def create_shipment_tracking(self, **_params):
        return self._create()

    @http.route([f"{b}/shipmentTracking/<string:rid>" for b in API_BASES], type="http", auth="public", methods=["GET"], csrf=False)
    def get_shipment_tracking(self, rid, **params):
        return self._get(rid, **params)

    @http.route([f"{b}/shipmentTracking/<string:rid>" for b in API_BASES], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_shipment_tracking(self, rid, **_params):
        return self._patch(rid)

    @http.route([f"{b}/shipmentTracking/<string:rid>" for b in API_BASES], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_shipment_tracking(self, rid, **_params):
        return self._delete(rid)

    @http.route([f"{b}/hub" for b in API_BASES], type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf684-shipmentTracking-{callback}",
                "api_name": "shipmentTracking",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route([f"{b}/hub/<string:sid>" for b in API_BASES], type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "shipmentTracking":
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route([f"{b}/listener/shipmentTrackingCreateEvent" for b in API_BASES], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tracking_create(self, **_params):
        return self._listener_ok()

    @http.route([f"{b}/listener/shipmentTrackingAttributeValueChangeEvent" for b in API_BASES], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tracking_change(self, **_params):
        return self._listener_ok()

    @http.route([f"{b}/listener/shipmentTrackingStateChangeEvent" for b in API_BASES], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tracking_state(self, **_params):
        return self._listener_ok()

    @http.route([f"{b}/listener/shipmentTrackingDeleteEvent" for b in API_BASES], type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tracking_delete(self, **_params):
        return self._listener_ok()
