from odoo import http
from odoo.http import request
import json

class TMFBillingController(http.Controller):

    # TMF666: List Billing Accounts
    @http.route('/tmf-api/accountManagement/v4/billingAccount', type='http', auth='public', methods=['GET'], csrf=False)
    def get_accounts(self, **params):
        accounts = request.env['tmf.billing.account'].sudo().search([])
        return request.make_response(
            json.dumps([a.to_tmf_json() for a in accounts]),
            headers=[('Content-Type', 'application/json')]
        )

    # TMF678: List Customer Bills (Invoices)
    @http.route('/tmf-api/customerBillManagement/v4/customerBill', type='http', auth='public', methods=['GET'], csrf=False)
    def get_bills(self, **params):
        # Filter only posted invoices
        domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]
        invoices = request.env['account.move'].sudo().search(domain)
        return request.make_response(
            json.dumps([i.to_tmf_json() for i in invoices]),
            headers=[('Content-Type', 'application/json')]
        )