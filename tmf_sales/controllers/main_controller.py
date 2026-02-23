import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/sales/v4"


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
    model = request.env["tmf.sales.lead"].sudo()
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


class TMF699SalesController(http.Controller):
    @http.route(f"{API_BASE}/salesLead", type="http", auth="public", methods=["GET"], csrf=False)
    def list_sales_lead(self, **params):
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.sales.lead"].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/salesLead", type="http", auth="public", methods=["POST"], csrf=False)
    def create_sales_lead(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        name = data.get("name")
        if not name:
            return _error(400, "Missing mandatory attribute: name")
        vals = {
            "name": name,
            "status": data.get("status") or "new",
            "description": data.get("description"),
            "priority": data.get("priority"),
            "expected_close_date": data.get("expectedCloseDate"),
            "creation_date_tmf": data.get("creationDate"),
            "status_change_date_tmf": data.get("statusChangeDate"),
            "related_party": data.get("relatedParty") or [],
            "category": data.get("category") or {},
            "channel": data.get("channel") or {},
            "market_segment": data.get("marketSegment") or {},
            "marketing_campaign": data.get("marketingCampaign") or {},
            "sales_opportunity": data.get("salesOpportunity") or {},
            "product": data.get("product") or [],
            "product_offering": data.get("productOffering") or [],
            "product_specification": data.get("productSpecification") or [],
            "target_product_schema": data.get("targetProductSchema") or {},
            "extra_json": {
                k: v
                for k, v in data.items()
                if k
                not in {
                    "name",
                    "status",
                    "description",
                    "priority",
                    "expectedCloseDate",
                    "creationDate",
                    "statusChangeDate",
                    "relatedParty",
                    "category",
                    "channel",
                    "marketSegment",
                    "marketingCampaign",
                    "salesOpportunity",
                    "product",
                    "productOffering",
                    "productSpecification",
                    "targetProductSchema",
                    "id",
                    "href",
                }
            },
        }
        rec = request.env["tmf.sales.lead"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/salesLead/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_sales_lead(self, rid, **params):
        rec = _find_by_rid(rid)
        if not rec:
            return _error(404, f"SalesLead {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/salesLead/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_sales_lead(self, rid, **_params):
        rec = _find_by_rid(rid)
        if not rec:
            return _error(404, f"SalesLead {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")

        vals = {}
        if "name" in patch:
            vals["name"] = patch.get("name")
        if "status" in patch:
            vals["status"] = patch.get("status")
        if "creationDate" in patch:
            vals["creation_date_tmf"] = patch.get("creationDate")
        if "statusChangeDate" in patch:
            vals["status_change_date_tmf"] = patch.get("statusChangeDate")
        if "description" in patch:
            vals["description"] = patch.get("description")
        if "priority" in patch:
            vals["priority"] = patch.get("priority")
        if "expectedCloseDate" in patch:
            vals["expected_close_date"] = patch.get("expectedCloseDate")
        if "relatedParty" in patch:
            vals["related_party"] = patch.get("relatedParty") or []
        if "category" in patch:
            vals["category"] = patch.get("category") or {}
        if "channel" in patch:
            vals["channel"] = patch.get("channel") or {}
        if "marketSegment" in patch:
            vals["market_segment"] = patch.get("marketSegment") or {}
        if "marketingCampaign" in patch:
            vals["marketing_campaign"] = patch.get("marketingCampaign") or {}
        if "salesOpportunity" in patch:
            vals["sales_opportunity"] = patch.get("salesOpportunity") or {}
        if "product" in patch:
            vals["product"] = patch.get("product") or []
        if "productOffering" in patch:
            vals["product_offering"] = patch.get("productOffering") or []
        if "productSpecification" in patch:
            vals["product_specification"] = patch.get("productSpecification") or []
        if "targetProductSchema" in patch:
            vals["target_product_schema"] = patch.get("targetProductSchema") or {}

        extra = rec.extra_json.copy() if isinstance(rec.extra_json, dict) else {}
        for k, v in patch.items():
            if k not in {
                "name",
                "status",
                "description",
                "priority",
                "expectedCloseDate",
                "creationDate",
                "statusChangeDate",
                "relatedParty",
                "category",
                "channel",
                "marketSegment",
                "marketingCampaign",
                "salesOpportunity",
                "product",
                "productOffering",
                "productSpecification",
                "targetProductSchema",
                "id",
                "href",
            }:
                extra[k] = v
        vals["extra_json"] = extra

        rec.sudo().write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/salesLead/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_sales_lead(self, rid, **_params):
        rec = _find_by_rid(rid)
        if not rec:
            return _error(404, f"SalesLead {rid} not found")
        rec.sudo().unlink()
        return request.make_response("", status=204)

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
                "name": f"tmf699-sales-{callback}",
                "api_name": "salesLead",
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
        if not rec or not rec.exists() or rec.api_name != "salesLead":
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/salesLeadCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_sales_lead_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/salesLeadAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_sales_lead_attribute_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/salesLeadStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_sales_lead_state_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/salesLeadDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_sales_lead_delete(self, **_params):
        return self._listener_ok()
