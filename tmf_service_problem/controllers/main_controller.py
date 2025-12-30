from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/serviceProblemManagement/v4/ServiceProblem', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.service.problem'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/serviceProblemManagement/v4/ServiceProblem', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['affected_number_of_services', 'category', 'creation_date', 'description', 'impact_importance_factor', 'last_update', 'name', 'originating_system', 'priority', 'problem_escalation', 'reason', 'resolution_date', 'status_change_date', 'status_change_reason', 'affected_location', 'affected_resource', 'affected_service', 'characteristic', 'external_identifier', 'first_alert', 'impact_pattern', 'note', 'originator_party', 'parent_problem', 'related_entity', 'related_event', 'related_party', 'responsible_party', 'root_cause_resource', 'root_cause_service', 'sla_violation', 'status', 'tracking_record', 'trouble_ticket', 'underlying_alarm', 'underlying_problem']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.service.problem'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
