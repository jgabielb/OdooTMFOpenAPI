import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/shippingOrder/v4.0"


def _json_response(payload, status=200, headers=None):
    base_headers = [("Content-Type", "application/json")]
    if headers:
        base_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=base_headers, status=status)


def _error(status, reason):
    status_str = str(status)
    return _json_response({"error": {"code": status_str, "status": status_str, "reason": reason}}, status=status)


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


def _find_by_rid(rid):
    model = request.env["tmf.shipping.order"].sudo()
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


def _build_vals(data):
    return {
        "external_id": data.get("externalId"),
        "state": data.get("state"),
        "creation_date": data.get("creationDate"),
        "status_change_date": data.get("statusChangeDate"),
        "shipping_order_date": data.get("shippingOrderDate"),
        "expected_shipping_start_date": data.get("expectedShippingStartDate"),
        "expected_shipping_completion_date": data.get("expectedShippingCompletionDate"),
        "completion_date": data.get("completionDate"),
        "requested_shipping_start_date": data.get("requestedShippingStartDate"),
        "requested_shipping_completion_date": data.get("requestedShippingCompletionDate"),
        "note": data.get("note") or [],
        "shipping_order_item": data.get("shippingOrderItem") or [],
        "related_party": data.get("relatedParty") or [],
        "related_shipping_order": data.get("relatedShippingOrder") or [],
        "related_shipment": data.get("relatedShipment") or [],
        "place": data.get("place") or [],
        "extra_json": {
            k: v
            for k, v in data.items()
            if k
            not in {
                "externalId",
                "state",
                "creationDate",
                "statusChangeDate",
                "shippingOrderDate",
                "expectedShippingStartDate",
                "expectedShippingCompletionDate",
                "completionDate",
                "requestedShippingStartDate",
                "requestedShippingCompletionDate",
                "note",
                "shippingOrderItem",
                "relatedParty",
                "relatedShippingOrder",
                "relatedShipment",
                "place",
                "id",
                "href",
            }
        },
    }


class TMF700ShippingOrderController(http.Controller):
    @http.route(f"{API_BASE}/shippingOrder", type="http", auth="public", methods=["GET"], csrf=False)
    def list_shipping_order(self, **params):
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.shipping.order"].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/shippingOrder", type="http", auth="public", methods=["POST"], csrf=False)
    def create_shipping_order(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        if not data.get("shippingOrderItem"):
            return _error(400, "Missing mandatory attribute: shippingOrderItem")
        rec = request.env["tmf.shipping.order"].sudo().create(_build_vals(data))
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/shippingOrder/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_shipping_order(self, rid, **params):
        rec = _find_by_rid(rid)
        if not rec:
            return _error(404, f"ShippingOrder {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/shippingOrder/<string:rid>", type="http", auth="public", methods=["PUT"], csrf=False)
    def put_shipping_order(self, rid, **_params):
        rec = _find_by_rid(rid)
        if not rec:
            return _error(404, f"ShippingOrder {rid} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        if not data.get("shippingOrderItem"):
            return _error(400, "Missing mandatory attribute: shippingOrderItem")
        rec.sudo().write(_build_vals(data))
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/shippingOrder/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_shipping_order(self, rid, **_params):
        rec = _find_by_rid(rid)
        if not rec:
            return _error(404, f"ShippingOrder {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        vals = _build_vals(patch)
        rec.sudo().write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf700-shipping-{callback}",
                "api_name": "shippingOrder",
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
        if not rec or not rec.exists() or rec.api_name != "shippingOrder":
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/shippingOrderCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipping_order_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shippingOrderAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipping_order_attr_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shippingOrderDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipping_order_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shippingOrderStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipping_order_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shippingOrderInformationRequiredEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shipping_order_info_required(self, **_params):
        return self._listener_ok()
