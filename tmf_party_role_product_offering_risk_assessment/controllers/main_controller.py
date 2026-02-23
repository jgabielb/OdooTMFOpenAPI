import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/riskManagement/v4"

RESOURCE_SPECS = {
    "productOfferingRiskAssessment": {
        "model": "tmf.product.offering.risk.assessment",
        "required": ["productOffering"],
        "tmf_map": {"status": "status", "characteristic": "characteristic", "place": "place", "riskAssessmentResult": "risk_assessment_result", "productOffering": "product_offering"},
    },
    "partyRoleRiskAssessment": {
        "model": "tmf.party.role.risk.assessment",
        "required": ["partyRole"],
        "tmf_map": {"status": "status", "characteristic": "characteristic", "place": "place", "riskAssessmentResult": "risk_assessment_result", "partyRole": "party_role"},
    },
    "partyRoleProductOfferingRiskAssessment": {
        "model": "tmf.party.role.product.offering.risk.assessment",
        "required": ["partyRole", "productOffering"],
        "tmf_map": {
            "status": "status",
            "characteristic": "characteristic",
            "place": "place",
            "riskAssessmentResult": "risk_assessment_result",
            "partyRole": "party_role",
            "productOffering": "product_offering",
        },
    },
    "shoppingCartRiskAssessment": {
        "model": "tmf.shopping.cart.risk.assessment",
        "required": ["shoppingCart"],
        "tmf_map": {"status": "status", "characteristic": "characteristic", "place": "place", "riskAssessmentResult": "risk_assessment_result", "shoppingCart": "shopping_cart"},
    },
    "productOrderRiskAssessment": {
        "model": "tmf.product.order.risk.assessment",
        "required": ["productOrder"],
        "tmf_map": {"status": "status", "characteristic": "characteristic", "place": "place", "riskAssessmentResult": "risk_assessment_result", "productOrder": "product_order"},
    },
}


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


def _find_by_rid(model_name, rid):
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
    return {
        "id": str(rec.id),
        "callback": rec.callback,
        "query": rec.query or "",
    }


def _build_create_vals(spec, data):
    vals = {}
    mapped = spec["tmf_map"]
    for tmf_key, odoo_field in mapped.items():
        if tmf_key in data:
            vals[odoo_field] = data.get(tmf_key)
    vals["extra_json"] = {k: v for k, v in data.items() if k not in set(mapped.keys()) | {"id", "href"}}
    return vals


def _validate_required(spec, data):
    missing = [key for key in spec["required"] if data.get(key) in (None, "", [], {})]
    return missing


class TMF696RiskManagementController(http.Controller):
    def _list_resource(self, resource_name, **params):
        spec = RESOURCE_SPECS[resource_name]
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("status") and str(params.get("status")).lower() != "undefined":
            domain.append(("status", "=", params["status"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env[spec["model"]].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _create_resource(self, resource_name, **_params):
        spec = RESOURCE_SPECS[resource_name]
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        missing = _validate_required(spec, data)
        if missing:
            return _error(400, f"Missing mandatory attribute(s): {', '.join(missing)}")
        vals = _build_create_vals(spec, data)
        rec = request.env[spec["model"]].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    def _get_resource(self, resource_name, rid, **params):
        spec = RESOURCE_SPECS[resource_name]
        rec = _find_by_rid(spec["model"], rid)
        if not rec:
            return _error(404, f"{resource_name} {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    def _delete_resource(self, resource_name, rid, **_params):
        spec = RESOURCE_SPECS[resource_name]
        rec = _find_by_rid(spec["model"], rid)
        if not rec:
            return _error(404, f"{resource_name} {rid} not found")
        rec.sudo().unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/productOfferingRiskAssessment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_product_offering_risk_assessment(self, **params):
        return self._list_resource("productOfferingRiskAssessment", **params)

    @http.route(f"{API_BASE}/productOfferingRiskAssessment", type="http", auth="public", methods=["POST"], csrf=False)
    def create_product_offering_risk_assessment(self, **params):
        return self._create_resource("productOfferingRiskAssessment", **params)

    @http.route(f"{API_BASE}/productOfferingRiskAssessment/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_product_offering_risk_assessment(self, rid, **params):
        return self._get_resource("productOfferingRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/productOfferingRiskAssessment/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_product_offering_risk_assessment(self, rid, **params):
        return self._delete_resource("productOfferingRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/partyRoleRiskAssessment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_party_role_risk_assessment(self, **params):
        return self._list_resource("partyRoleRiskAssessment", **params)

    @http.route(f"{API_BASE}/partyRoleRiskAssessment", type="http", auth="public", methods=["POST"], csrf=False)
    def create_party_role_risk_assessment(self, **params):
        return self._create_resource("partyRoleRiskAssessment", **params)

    @http.route(f"{API_BASE}/partyRoleRiskAssessment/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_party_role_risk_assessment(self, rid, **params):
        return self._get_resource("partyRoleRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/partyRoleRiskAssessment/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_party_role_risk_assessment(self, rid, **params):
        return self._delete_resource("partyRoleRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/partyRoleProductOfferingRiskAssessment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_party_role_product_offering_risk_assessment(self, **params):
        return self._list_resource("partyRoleProductOfferingRiskAssessment", **params)

    @http.route(f"{API_BASE}/partyRoleProductOfferingRiskAssessment", type="http", auth="public", methods=["POST"], csrf=False)
    def create_party_role_product_offering_risk_assessment(self, **params):
        return self._create_resource("partyRoleProductOfferingRiskAssessment", **params)

    @http.route(f"{API_BASE}/partyRoleProductOfferingRiskAssessment/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_party_role_product_offering_risk_assessment(self, rid, **params):
        return self._get_resource("partyRoleProductOfferingRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/partyRoleProductOfferingRiskAssessment/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_party_role_product_offering_risk_assessment(self, rid, **params):
        return self._delete_resource("partyRoleProductOfferingRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/shoppingCartRiskAssessment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_shopping_cart_risk_assessment(self, **params):
        return self._list_resource("shoppingCartRiskAssessment", **params)

    @http.route(f"{API_BASE}/shoppingCartRiskAssessment", type="http", auth="public", methods=["POST"], csrf=False)
    def create_shopping_cart_risk_assessment(self, **params):
        return self._create_resource("shoppingCartRiskAssessment", **params)

    @http.route(f"{API_BASE}/shoppingCartRiskAssessment/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_shopping_cart_risk_assessment(self, rid, **params):
        return self._get_resource("shoppingCartRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/shoppingCartRiskAssessment/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_shopping_cart_risk_assessment(self, rid, **params):
        return self._delete_resource("shoppingCartRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/productOrderRiskAssessment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_product_order_risk_assessment(self, **params):
        return self._list_resource("productOrderRiskAssessment", **params)

    @http.route(f"{API_BASE}/productOrderRiskAssessment", type="http", auth="public", methods=["POST"], csrf=False)
    def create_product_order_risk_assessment(self, **params):
        return self._create_resource("productOrderRiskAssessment", **params)

    @http.route(f"{API_BASE}/productOrderRiskAssessment/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_product_order_risk_assessment(self, rid, **params):
        return self._get_resource("productOrderRiskAssessment", rid, **params)

    @http.route(f"{API_BASE}/productOrderRiskAssessment/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_product_order_risk_assessment(self, rid, **params):
        return self._delete_resource("productOrderRiskAssessment", rid, **params)

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
                "name": f"tmf696-risk-{callback}",
                "api_name": "partyRoleProductOfferingRiskAssessment",
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
        if not rec or not rec.exists():
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/productOfferingRiskAssessmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/productOfferingRiskAssessmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/productOfferingRiskAssessmentStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_offering_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleRiskAssessmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleRiskAssessmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleRiskAssessmentStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleProductOfferingRiskAssessmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_product_offering_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleProductOfferingRiskAssessmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_product_offering_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleProductOfferingRiskAssessmentStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_product_offering_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shoppingCartRiskAssessmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shopping_cart_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shoppingCartRiskAssessmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shopping_cart_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/shoppingCartRiskAssessmentStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_shopping_cart_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/productOrderRiskAssessmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_order_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/productOrderRiskAssessmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_order_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/productOrderRiskAssessmentStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_product_order_status(self, **_params):
        return self._listener_ok()
