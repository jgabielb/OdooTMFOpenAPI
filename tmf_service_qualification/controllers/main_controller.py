from odoo import http
from odoo.http import request
import json

class TMFQualificationController(http.Controller):

    # GET: List history of checks
    @http.route('/tmf-api/serviceQualificationManagement/v4/checkServiceQualification', type='http', auth='public', methods=['GET'], csrf=False)
    def get_qualifications(self, **params):
        records = request.env['tmf.service.qualification'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    # POST: Run a new check
    @http.route('/tmf-api/serviceQualificationManagement/v4/checkServiceQualification', type='http', auth='public', methods=['POST'], csrf=False)
    def check_qualification(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}

            # 1. Extract Address (Place)
            # Incoming JSON: "place": {"id": "UUID", "@type": "GeographicAddress"}
            place_info = data.get('place', {})
            place_id_tmf = place_info.get('id')
            if place_id_tmf:
                addr = request.env['tmf.geographic.address'].sudo().search([('tmf_id', '=', place_id_tmf)], limit=1)
                if addr:
                    vals['place_id'] = addr.id
            
            # 2. Extract Specification
            # Incoming JSON: "serviceSpecification": {"id": "UUID"}
            spec_info = data.get('serviceSpecification', {})
            spec_id_tmf = spec_info.get('id')
            if spec_id_tmf:
                spec = request.env['tmf.product.specification'].sudo().search([('tmf_id', '=', spec_id_tmf)], limit=1)
                if spec:
                    vals['service_specification_id'] = spec.id

            # Validation
            if 'place_id' not in vals or 'service_specification_id' not in vals:
                return request.make_response(
                    json.dumps({'code': 400, 'message': 'Missing Place (Address) or ServiceSpecification ID'}),
                    status=400
                )

            # 3. Create (Runs logic automatically)
            new_check = request.env['tmf.service.qualification'].sudo().create(vals)
            
            return request.make_response(
                json.dumps(new_check.to_tmf_json()),
                status=201, # Created
                headers=[('Content-Type', 'application/json')]
            )

        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=500)