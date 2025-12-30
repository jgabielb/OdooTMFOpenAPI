from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/transferBalanceManagement/v4/TransferBalance', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.transfer.balance'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/transferBalanceManagement/v4/TransferBalance', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['confirmation_date', 'cost_owner', 'description', 'reason', 'receiver_bucket_usage_type', 'requested_date', 'status', 'usage_type', 'amount', 'bucket', 'channel', 'impacted_bucket', 'logical_resource', 'party_account', 'product', 'receiver', 'receiver_bucket', 'receiver_logical_resource', 'receiver_party_account', 'receiver_product', 'related_party', 'requestor', 'transfer_cost']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.transfer.balance'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
