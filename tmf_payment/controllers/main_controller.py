from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/paymentManagement/v4/Payment', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.payment'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/paymentManagement/v4/Payment', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['authorization_code', 'correlator_id', 'description', 'name', 'payment_date', 'status', 'status_date', 'account', 'amount', 'channel', 'payment_item', 'payment_method', 'point_of_interaction', 'related_party', 'tax_amount', 'total_amount']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.payment'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
