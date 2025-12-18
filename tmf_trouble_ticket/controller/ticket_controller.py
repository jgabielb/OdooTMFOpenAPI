from odoo import http
from odoo.http import request
import json

class TMFTicketController(http.Controller):

    # GET Tickets
    @http.route('/tmf-api/troubleTicketManagement/v4/troubleTicket', type='http', auth='public', methods=['GET'], csrf=False)
    def get_tickets(self, **params):
        tickets = request.env['tmf.trouble.ticket'].sudo().search([])
        return request.make_response(
            json.dumps([t.to_tmf_json() for t in tickets]),
            headers=[('Content-Type', 'application/json')]
        )

    # POST Ticket (Create)
    @http.route('/tmf-api/troubleTicketManagement/v4/troubleTicket', type='http', auth='public', methods=['POST'], csrf=False)
    def create_ticket(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {
                'description': data.get('description'),
                'severity': data.get('severity', 'Medium'),
                'type': data.get('type', 'Complaint'),
                'status': 'Submitted'
            }

            # Link Customer
            for party in data.get('relatedParty', []):
                if party.get('role') == 'Customer':
                    partner = request.env['res.partner'].sudo().search([('tmf_id', '=', party.get('id'))], limit=1)
                    if partner:
                        vals['partner_id'] = partner.id

            # Link Service
            for entity in data.get('relatedEntity', []):
                if entity.get('@referredType') == 'Service':
                    service = request.env['tmf.service'].sudo().search([('tmf_id', '=', entity.get('id'))], limit=1)
                    if service:
                        vals['service_id'] = service.id

            new_ticket = request.env['tmf.trouble.ticket'].sudo().create(vals)
            
            return request.make_response(
                json.dumps(new_ticket.to_tmf_json()),
                status=201,
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)