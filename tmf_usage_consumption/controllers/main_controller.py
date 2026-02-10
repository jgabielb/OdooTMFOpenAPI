# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import uuid

API_BASE = "/tmf-api/usageConsumptionManagement/v5"

def _json_response(payload, status=200):
    return request.make_response(
    json.dumps(payload),
    headers=[("Content-Type", "application/json")],
    status=status,
    )
def _parse_body():
    raw = request.httprequest.data or b"{}"
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    raw = raw.strip() or "{}"
    return json.loads(raw)

class TMFUsageConsumptionController(http.Controller):

    # -------------------------
    # QueryUsageConsumption
    # -------------------------
    @http.route(f"{API_BASE}/queryUsageConsumption", type="http", auth="public", methods=["GET"], csrf=False)
    def list_query_usage_consumption(self, **params):
        fields_filter = params.get("fields")
        dom = []
        if params.get("id"):
            dom.append(("tmf_id", "=", params["id"]))

        recs = request.env["tmf.query.usage.consumption"].sudo().search(dom)

        out = [r.to_tmf_json(fields_filter=fields_filter) for r in recs]
        return _json_response(out, status=200)

    @http.route(f"{API_BASE}/queryUsageConsumption/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_query_usage_consumption(self, rid, **params):
        fields_filter = params.get("fields")
        rec = request.env["tmf.query.usage.consumption"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)

        payload = rec.to_tmf_json(fields_filter=fields_filter)
        return _json_response(payload, status=200)

    @http.route(f"{API_BASE}/queryUsageConsumption", type="http", auth="public", methods=["POST"], csrf=False)
    def create_query_usage_consumption(self, **params):
        try:
            data = _parse_body()

            tmf_type = data.get("@type")
            if not tmf_type:
                return _json_response({"error": "Missing mandatory attribute '@type'."}, status=400)

            # Persist the Query resource
            vals = {
                "tmf_type": tmf_type,
                "usage_consumption_json": json.dumps(data.get("usageConsumption") or []),
                "party_account_json": json.dumps(data.get("partyAccount")) if data.get("partyAccount") is not None else None,
                "related_party_json": json.dumps(data.get("relatedParty")) if data.get("relatedParty") is not None else None,
                "search_criteria_json": json.dumps(data.get("searchCriteria")) if data.get("searchCriteria") is not None else None,
                "error_message_json": json.dumps(data.get("errorMessage")) if data.get("errorMessage") is not None else None,
            }

            rec = request.env["tmf.query.usage.consumption"].sudo().create(vals)

            # Fix for CTK: The Query response includes a searchCriteria.href pointing to 
            # /usageConsumptionReport/{id}. The CTK follows this link.
            # We must ensure a Report exists with this ID to avoid 404.
            report_vals = {
                "tmf_id": rec.tmf_id,
                "tmf_type": "UsageConsumptionReport",
                "bucket_json": "[]"  # Initialize with empty bucket list
            }
            request.env["tmf.usage.consumption.report"].sudo().create(report_vals)

            payload = rec.to_tmf_json(fields_filter=params.get("fields"))
            return _json_response(payload, status=201)

        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    # -------------------------
    # UsageConsumptionReport
    # -------------------------
    @http.route(f"{API_BASE}/usageConsumptionReport", type="http", auth="public", methods=["GET"], csrf=False)
    def list_usage_consumption_report(self, **params):
        fields_filter = params.get("fields")
        dom = []
        if params.get("id"):
            dom.append(("tmf_id", "=", params["id"]))

        recs = request.env["tmf.usage.consumption.report"].sudo().search(dom)
        return _json_response([r.to_tmf_json(fields_filter=fields_filter) for r in recs], status=200)

    @http.route(f"{API_BASE}/usageConsumptionReport/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_usage_consumption_report(self, rid, **params):
        fields_filter = params.get("fields")
        rec = request.env["tmf.usage.consumption.report"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)
        return _json_response(rec.to_tmf_json(fields_filter=fields_filter), status=200)
