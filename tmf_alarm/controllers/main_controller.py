from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/alarmManagement/v4/Alarm', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.alarm'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/alarmManagement/v4/Alarm', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['ack_state', 'ack_system_id', 'ack_user_id', 'alarm_changed_time', 'alarm_cleared_time', 'alarm_details', 'alarm_escalation', 'alarm_raised_time', 'alarm_reporting_time', 'alarmed_object_type', 'clear_system_id', 'clear_user_id', 'external_alarm_id', 'is_root_cause', 'planned_outage_indicator', 'probable_cause', 'proposed_repaired_actions', 'reporting_system_id', 'service_affecting', 'source_system_id', 'specific_problem', 'state', 'affected_service', 'alarm_type', 'alarmed_object', 'comment', 'correlated_alarm', 'crossed_threshold_information', 'parent_alarm', 'perceived_severity', 'place']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.alarm'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
