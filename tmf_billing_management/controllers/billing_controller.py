from odoo import http, fields
from odoo.http import request
import json
import uuid


class TMFBillingController(http.Controller):

    # TMF666: Create Billing Account
    @http.route('/tmf-api/accountManagement/v4/billingAccount', type='http', auth='public', methods=['POST'], csrf=False)
    def create_account(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")
            # Resolve partner from relatedParty
            partner_id = False
            for rp in (data.get("relatedParty") or []):
                if not isinstance(rp, dict):
                    continue
                rp_id = rp.get("id")
                if rp_id:
                    partner = request.env["res.partner"].sudo().search([("tmf_id", "=", str(rp_id))], limit=1)
                    if not partner and str(rp_id).isdigit():
                        partner = request.env["res.partner"].sudo().browse(int(rp_id))
                    if partner and partner.exists():
                        partner_id = partner.id
                        break
            if not partner_id:
                # Create a minimal partner so we always satisfy the required field
                partner_id = request.env["res.partner"].sudo().create({"name": data.get("name") or "BillingAccountHolder"}).id

            rec = request.env["tmf.billing.account"].sudo().create({
                "name": data.get("name") or "Billing Account",
                "partner_id": partner_id,
                "state": data.get("state") or "active",
            })
            return request.make_response(
                json.dumps(rec.to_tmf_json()),
                headers=[("Content-Type", "application/json")],
                status=201,
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=400,
            )

    # TMF666: Get Billing Account by ID
    @http.route('/tmf-api/accountManagement/v4/billingAccount/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_account(self, tmf_id, **params):
        rec = request.env["tmf.billing.account"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return request.make_response(json.dumps({"error": "Not Found"}), headers=[("Content-Type", "application/json")], status=404)
        return request.make_response(json.dumps(rec.to_tmf_json()), headers=[("Content-Type", "application/json")])

    # TMF666: List Billing Accounts
    @http.route('/tmf-api/accountManagement/v4/billingAccount', type='http', auth='public', methods=['GET'], csrf=False)
    def get_accounts(self, **params):
        try:
            limit = max(1, min(int(params.get('limit') or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get('offset') or 0))
        except (ValueError, TypeError):
            offset = 0
        env = request.env['tmf.billing.account'].sudo()
        accounts = env.search([], limit=limit, offset=offset, order='id asc')
        total = env.search_count([])
        data = [a.to_tmf_json() for a in accounts]
        return request.make_response(
            json.dumps(data),
            headers=[
                ('Content-Type', 'application/json'),
                ('X-Total-Count', str(total)),
                ('X-Result-Count', str(len(data))),
            ]
        )

    # TMF678: List Customer Bills (Invoices)
    @http.route('/tmf-api/customerBillManagement/v4/customerBill', type='http', auth='public', methods=['GET'], csrf=False)
    def get_bills(self, **params):
        try:
            limit = max(1, min(int(params.get('limit') or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get('offset') or 0))
        except (ValueError, TypeError):
            offset = 0
        # Filter only posted invoices
        domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]
        env = request.env['account.move'].sudo()
        invoices = env.search(domain, limit=limit, offset=offset, order='id asc')
        total = env.search_count(domain)
        data = [i.to_tmf_json() for i in invoices]
        return request.make_response(
            json.dumps(data),
            headers=[
                ('Content-Type', 'application/json'),
                ('X-Total-Count', str(total)),
                ('X-Result-Count', str(len(data))),
            ]
        )