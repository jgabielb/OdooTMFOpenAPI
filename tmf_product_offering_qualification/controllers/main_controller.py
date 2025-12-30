from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/productOfferingQualificationManagement/v4/ProductOfferingQualification', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.product.offering.qualification'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/productOfferingQualificationManagement/v4/ProductOfferingQualification', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['effective_qualification_date', 'expected_poq_completion_date', 'instant_sync_qualification', 'project_id', 'provide_alternative', 'requested_poq_completion_date', 'product_offering_qualification_item', 'related_party', 'state', 'state_change']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.product.offering.qualification'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
