from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import json

API_BASE = "/tmf-api/paymentManagement/v4"

def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=[("Content-Type", "application/json")],
        status=status,
    )

class TMF676Controller(http.Controller):

    # LIST /payment
    @http.route(f"{API_BASE}/payment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_payment(self, **params):
        fields_sel = params.get("fields")  # comma-separated
        if fields_sel:
            requested = set([f.strip() for f in fields_sel.split(",") if f.strip()])
            # CTK expects id always present, even if only href requested
            requested.add("id")
            # keep href too (safe)
            requested.add("href")
            fields_sel = ",".join(sorted(requested))

        # minimal filtering (optional per conformance for sub-resources)
        domain = []
        recs = request.env["tmf.payment"].sudo().search(domain)

        host_url = request.httprequest.host_url.rstrip("/")
        data = [r.to_tmf_json(host_url=host_url, fields_filter=fields_sel) for r in recs]
        return _json_response(data, status=200)

    # GET /payment/{id}
    @http.route(f"{API_BASE}/payment/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_payment(self, tmf_id, **params):
        fields_sel = params.get("fields")
        rec = request.env["tmf.payment"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)

        host_url = request.httprequest.host_url.rstrip("/")
        return _json_response(rec.to_tmf_json(host_url=host_url, fields_filter=fields_sel), status=200)

    # POST /payment
    @http.route(f"{API_BASE}/payment", type="http", auth="public", methods=["POST"], csrf=False)
    def create_payment(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")

            # enforce mandatory POST attributes (per conformance profile)
            if not isinstance(data, dict):
                raise ValidationError("Payload must be a JSON object.")

            account = data.get("account")
            if not isinstance(account, dict) or not account.get("id"):
                raise ValidationError("TMF676: 'account.id' is mandatory.")
            payment_method = data.get("paymentMethod")
            if not isinstance(payment_method, dict):
                raise ValidationError("TMF676: 'paymentMethod' is mandatory and must be an object.")
            total = data.get("totalAmount")
            if not isinstance(total, dict) or total.get("unit") in (None, "") or total.get("value") in (None, ""):
                raise ValidationError("TMF676: 'totalAmount.unit' and 'totalAmount.value' are mandatory.")

            # store JSON fields
            vals = {
                "authorization_code": data.get("authorizationCode"),
                "correlator_id": data.get("correlatorId"),
                "description": data.get("description"),
                "name": data.get("name"),
                "payment_date": data.get("paymentDate"),
                "status": data.get("status"),
                "status_date": data.get("statusDate"),
                "account_json": json.dumps(account, ensure_ascii=False),
                "payment_method_json": json.dumps(payment_method, ensure_ascii=False),
                "total_amount_json": json.dumps(total, ensure_ascii=False),
            }

            if data.get("channel") is not None:
                vals["channel_json"] = json.dumps(data.get("channel"), ensure_ascii=False)
            if data.get("paymentItem") is not None:
                vals["payment_item_json"] = json.dumps(data.get("paymentItem"), ensure_ascii=False)

            rec = request.env["tmf.payment"].sudo().create(vals)

            host_url = request.httprequest.host_url.rstrip("/")
            return _json_response(rec.to_tmf_json(host_url=host_url), status=201)

        except ValidationError as ve:
            return _json_response({"error": str(ve)}, status=400)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)
