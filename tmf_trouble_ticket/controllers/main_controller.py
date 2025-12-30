from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/troubleTicketManagement/v4/TroubleTicket', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.trouble.ticket'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/troubleTicketManagement/v4/TroubleTicket', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['creation_date', 'description', 'expected_resolution_date', 'external_id', 'last_update', 'name', 'priority', 'requested_resolution_date', 'resolution_date', 'severity', 'status_change_date', 'status_change_reason', 'ticket_type', 'attachment', 'channel', 'note', 'related_entity', 'related_party', 'status', 'status_change', 'trouble_ticket_relationship']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.trouble.ticket'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
