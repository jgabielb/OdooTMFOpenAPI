from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/serviceLevelObjectiveManagement/v4/ServiceLevelObjective', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.service.level.objective'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/serviceLevelObjectiveManagement/v4/ServiceLevelObjective', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['conformance_comparator', 'conformance_target', 'grace_times', 'name', 'threshold_target', 'tolerance_target', 'conformance_period', 'service_level_objective_consequence', 'service_level_objective_parameter', 'tolerance_period', 'valid_for']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.service.level.objective'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
