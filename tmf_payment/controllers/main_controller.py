from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import json

API_BASE = "/tmf-api/paymentManagement/v4"

def _json_response(payload, status=200, headers=None):
    hdrs = [("Content-Type", "application/json")]
    if headers:
        hdrs.extend(headers)
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=hdrs,
        status=status,
    )

class TMF676Controller(http.Controller):

    # LIST /payment
    @http.route(f"{API_BASE}/payment", type="http", auth="public", methods=["GET"], csrf=False)
    def list_payment(self, **params):
        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
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
        env = request.env["tmf.payment"].sudo()
        recs = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)

        host_url = request.httprequest.host_url.rstrip("/")
        data = [r.to_tmf_json(host_url=host_url, fields_filter=fields_sel) for r in recs]
        return _json_response(data, status=200, headers=[("X-Total-Count", str(total)), ("X-Result-Count", str(len(data)))])

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

            # Wire to native Odoo records when references exist
            partner_id = None
            account_id = account.get("id")
            if account_id:
                partner = request.env["res.partner"].sudo().search([("tmf_id", "=", str(account_id))], limit=1)
                if not partner and str(account_id).isdigit():
                    partner = request.env["res.partner"].sudo().browse(int(account_id))
                if partner and partner.exists():
                    partner_id = partner.id
                    vals["partner_id"] = partner_id

            invoice_ids = []
            payment_items = data.get("paymentItem")
            if isinstance(payment_items, list):
                for pi in payment_items:
                    item = pi.get("item") if isinstance(pi, dict) else None
                    iid = item.get("id") if isinstance(item, dict) else None
                    if not iid:
                        continue
                    move = request.env["account.move"].sudo().search([("tmf_id", "=", str(iid))], limit=1)
                    if not move and str(iid).isdigit():
                        move = request.env["account.move"].sudo().browse(int(iid))
                    if move and move.exists():
                        invoice_ids.append(move.id)
                        if not partner_id and move.partner_id:
                            vals["partner_id"] = move.partner_id.id

            if data.get("channel") is not None:
                vals["channel_json"] = json.dumps(data.get("channel"), ensure_ascii=False)
            if data.get("paymentItem") is not None:
                vals["payment_item_json"] = json.dumps(data.get("paymentItem"), ensure_ascii=False)

            rec = request.env["tmf.payment"].sudo().create(vals)
            if invoice_ids:
                rec.sudo().write({"invoice_ids": [(6, 0, invoice_ids)]})

            host_url = request.httprequest.host_url.rstrip("/")
            return _json_response(rec.to_tmf_json(host_url=host_url), status=201)

        except ValidationError as ve:
            return _json_response({"error": str(ve)}, status=400)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    # PATCH /payment/{id}
    @http.route(f"{API_BASE}/payment/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_payment(self, tmf_id, **params):
        try:
            rec = request.env["tmf.payment"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
            if not rec:
                return _json_response({"error": "Not found"}, status=404)

            data = json.loads(request.httprequest.data or b"{}")
            if not isinstance(data, dict):
                raise ValidationError("Payload must be a JSON object.")

            vals = {}
            if "authorizationCode" in data:
                vals["authorization_code"] = data.get("authorizationCode")
            if "correlatorId" in data:
                vals["correlator_id"] = data.get("correlatorId")
            if "description" in data:
                vals["description"] = data.get("description")
            if "name" in data:
                vals["name"] = data.get("name")
            if "paymentDate" in data:
                vals["payment_date"] = data.get("paymentDate")
            if "status" in data:
                vals["status"] = data.get("status")
            if "statusDate" in data:
                vals["status_date"] = data.get("statusDate")
            if "account" in data:
                account = data.get("account")
                if account is not None and (not isinstance(account, dict) or not account.get("id")):
                    raise ValidationError("TMF676: if provided, 'account.id' is mandatory.")
                vals["account_json"] = json.dumps(account, ensure_ascii=False) if account is not None else None
            if "paymentMethod" in data:
                payment_method = data.get("paymentMethod")
                if payment_method is not None and not isinstance(payment_method, dict):
                    raise ValidationError("TMF676: if provided, 'paymentMethod' must be an object.")
                vals["payment_method_json"] = json.dumps(payment_method, ensure_ascii=False) if payment_method is not None else None
            if "totalAmount" in data:
                total = data.get("totalAmount")
                if total is not None and (
                    not isinstance(total, dict)
                    or total.get("unit") in (None, "")
                    or total.get("value") in (None, "")
                ):
                    raise ValidationError("TMF676: if provided, 'totalAmount.unit' and 'totalAmount.value' are mandatory.")
                vals["total_amount_json"] = json.dumps(total, ensure_ascii=False) if total is not None else None
            if "channel" in data:
                vals["channel_json"] = json.dumps(data.get("channel"), ensure_ascii=False) if data.get("channel") is not None else None
            if "paymentItem" in data:
                vals["payment_item_json"] = json.dumps(data.get("paymentItem"), ensure_ascii=False) if data.get("paymentItem") is not None else None

            if vals:
                rec.sudo().write(vals)

            host_url = request.httprequest.host_url.rstrip("/")
            return _json_response(rec.to_tmf_json(host_url=host_url), status=200)
        except ValidationError as ve:
            return _json_response({"error": str(ve)}, status=400)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    # DELETE /payment/{id}
    @http.route(f"{API_BASE}/payment/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_payment(self, tmf_id, **params):
        rec = request.env["tmf.payment"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)
        rec.unlink()
        return request.make_response("", status=204)
