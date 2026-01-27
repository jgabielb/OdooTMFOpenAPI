from odoo import http, fields
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)

class TMFTicketController(http.Controller):

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    def _response(self, data, status=200):
        if isinstance(data, dict) and '@type' not in data:
             data['@type'] = 'TroubleTicket'
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and '@type' not in item:
                    item['@type'] = 'TroubleTicket'

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    def _error(self, status, code, message):
        return request.make_response(
            json.dumps({
                "code": str(code), 
                "message": message, 
                "reason": message,
                "status": str(status),
                "@type": "Error"
            }),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    def _filter_fields(self, data, fields_param):
        if not fields_param: return data
        requested = fields_param.split(',')
        mandatory = ['id', 'href', '@type']
        def filter_dict(d):
            return {k: v for k, v in d.items() if k in requested or k in mandatory}
        if isinstance(data, list):
            return [filter_dict(item) for item in data]
        return filter_dict(data)

    def _get_base_url(self):
        return request.httprequest.host_url.rstrip('/') + "/tmf-api/troubleTicketManagement/v5/troubleTicket"

    def _clean_date(self, iso_date_str):
        if not iso_date_str: return False
        try:
            dt = iso_date_str.replace('Z', '')
            if 'T' in dt: dt = dt.replace('T', ' ')
            if '.' in dt: dt = dt.split('.')[0]
            return dt
        except:
            return False

    # -------------------------------------------------------------------------
    # TMF621 v5 API Routes
    # -------------------------------------------------------------------------

    @http.route('/tmf-api/troubleTicketManagement/v5/troubleTicket', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def ticket_collection(self, **params):
        if request.httprequest.method == 'POST':
            return self._create_ticket()
        return self._list_tickets(**params)

    @http.route('/tmf-api/troubleTicketManagement/v5/troubleTicket/<string:id>', type='http', auth='public',
            methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def ticket_individual_str(self, id, **params):
        ticket = self._find_ticket(id)
        if not ticket:
            return self._error(404, "NOT_FOUND", f"TroubleTicket {id} not found")

        if request.httprequest.method == 'GET':
            return self._response(self._filter_fields(ticket.to_tmf_json(), params.get('fields')))
        elif request.httprequest.method == 'PATCH':
            return self._patch_ticket(ticket)
        elif request.httprequest.method == 'DELETE':
            try:
                ticket.unlink()
                return Response(status=204)
            except Exception as e:
                return self._error(400, "DELETE_ERROR", str(e))

    # -------------------------------------------------------------------------
    # Business Logic
    # -------------------------------------------------------------------------

    def _list_tickets(self, **params):
        domain = []
        if params.get('severity'):
            domain.append(('severity', '=', params.get('severity')))
        if params.get('type'):
            domain.append(('ticket_type', '=', params.get('type')))
        if params.get('status'):
            domain.append(('status', '=', params.get('status')))

        tickets = request.env['tmf.trouble.ticket'].sudo().search(domain, limit=50, order='id desc')
        data = [t.to_tmf_json() for t in tickets]
        return self._response(self._filter_fields(data, params.get('fields')))

    def _create_ticket(self):
        try:
            data = json.loads(request.httprequest.data)
            
            # --- Robust Defaults ---
            vals = {
                'name': data.get('name') or 'New Ticket',
                'description': data.get('description') or 'No description',
                # Pass strings directly now (Model is Char)
                'ticket_type': data.get('ticketType') or data.get('type') or 'Complaint',
                'priority': data.get('priority') or 'Medium',
                'severity': data.get('severity') or 'Medium',
                'status': data.get('status') or 'Submitted', 
                'status_change_reason': data.get('statusChangeReason')
            }

            if data.get('requestedResolutionDate'):
                vals['requested_resolution_date'] = self._clean_date(data['requestedResolutionDate'])
            if data.get('expectedResolutionDate'):
                vals['expected_resolution_date'] = self._clean_date(data['expectedResolutionDate'])

            if data.get('relatedParty'):
                for party in data['relatedParty']:
                    if party.get('role') == 'Customer' and party.get('id'):
                        if str(party['id']).isdigit():
                            vals['partner_id'] = int(party['id'])

            new_ticket = request.env['tmf.trouble.ticket'].sudo().create(vals)
            return self._response(new_ticket.to_tmf_json(), status=201)

        except Exception as e:
            _logger.exception("TMF621 Create Error")
            # If this still fails, it's a critical DB issue
            return self._error(400, "BAD_REQUEST", f"Creation failed: {str(e)}")

    def _patch_ticket(self, ticket):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Direct mapping allowed by Char fields
            if 'description' in data: vals['description'] = data['description']
            if 'name' in data: vals['name'] = data['name']
            if 'severity' in data: vals['severity'] = data['severity']
            if 'priority' in data: vals['priority'] = data['priority']
            if 'status' in data: vals['status'] = data['status']
            if 'statusChangeReason' in data: vals['status_change_reason'] = data['statusChangeReason']
            if 'ticketType' in data: vals['ticket_type'] = data['ticketType']
            
            if 'requestedResolutionDate' in data:
                vals['requested_resolution_date'] = self._clean_date(data['requestedResolutionDate'])

            if vals:
                ticket.write(vals)

            return self._response(ticket.to_tmf_json())
        except Exception as e:
            return self._error(400, "UPDATE_ERROR", str(e))
        
    def _find_ticket(self, id_value):
        Ticket = request.env['tmf.trouble.ticket'].sudo()
        s = str(id_value)

        # 1) Si es int, busca por id
        if s.isdigit():
            rec = Ticket.browse(int(s))
            if rec.exists():
                return rec

        # 2) Si manejas tmf_id, intenta por tmf_id
        if 'tmf_id' in Ticket._fields:
            rec = Ticket.search([('tmf_id', '=', s)], limit=1)
            if rec:
                return rec

        # 3) fallback por name (si tu name es tipo TT-2026...)
        rec = Ticket.search([('name', '=', s)], limit=1)
        return rec or False
