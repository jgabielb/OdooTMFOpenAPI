from odoo import http
from odoo.http import request
import json

class TMFBillingController(http.Controller):

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