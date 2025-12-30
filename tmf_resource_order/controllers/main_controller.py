from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/resourceOrderManagement/v4/ResourceOrder', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.resource.order'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/resourceOrderManagement/v4/ResourceOrder', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['cancellation_date', 'cancellation_reason', 'category', 'completion_date', 'description', 'expected_completion_date', 'external_id', 'name', 'order_date', 'order_type', 'priority', 'requested_completion_date', 'requested_start_date', 'start_date', 'external_reference', 'note', 'order_item', 'related_party', 'state']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.resource.order'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
