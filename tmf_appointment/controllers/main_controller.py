from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/appointmentManagement/v4/Appointment', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.appointment'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/appointmentManagement/v4/Appointment', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['category', 'creation_date', 'description', 'external_id', 'last_update', 'attachment', 'calendar_event', 'contact_medium', 'note', 'related_entity', 'related_party', 'related_place', 'status', 'valid_for']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.appointment'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
