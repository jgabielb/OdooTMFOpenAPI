from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/productManagement/v4/Product', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.product'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/productManagement/v4/Product', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['description', 'is_bundle', 'is_customer_visible', 'name', 'order_date', 'product_serial_number', 'random_att', 'start_date', 'termination_date', 'agreement', 'billing_account', 'place', 'product', 'product_characteristic', 'product_offering', 'product_order_item', 'product_price', 'product_relationship', 'product_specification', 'product_term', 'realizing_resource', 'realizing_service', 'related_party', 'status']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.product'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
