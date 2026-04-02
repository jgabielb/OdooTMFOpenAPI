from odoo import http, fields
from odoo.http import request, Response
import json
import logging

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

class TMFTicketController(TMFBaseController):

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    # NOTE: Do not override TMFBaseController._error.
    # We standardize on tmf_base error schema:
    #   {"code": "<http-status>", "reason": "...", "message": "..."}

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
            return self._json(self._select_fields(ticket.to_tmf_json(), params.get('fields')))
        elif request.httprequest.method == 'PATCH':
            return self._patch_ticket(ticket)
        elif request.httprequest.method == 'DELETE':
            try:
                ticket.unlink()
                return Response(status=204)
            except Exception as e:
                return self._error(400, "DELETE_ERROR", str(e))

    @http.route('/tmf-api/troubleTicketManagement/v5/troubleTicketSpecification', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def ticket_spec_collection(self, **params):
        if request.httprequest.method == 'POST':
            return self._create_specification()
        return self._list_specifications(**params)

    @http.route('/tmf-api/troubleTicketManagement/v5/troubleTicketSpecification/<string:id>', type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def ticket_spec_individual_str(self, id, **params):
        spec = self._find_specification(id)
        if not spec:
            return self._error(404, "NOT_FOUND", f"TroubleTicketSpecification {id} not found")

        if request.httprequest.method == 'GET':
            return self._json(self._select_fields(spec.to_tmf_json(), params.get('fields')))
        elif request.httprequest.method == 'PATCH':
            return self._patch_specification(spec)
        elif request.httprequest.method == 'DELETE':
            try:
                spec.unlink()
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

        limit, offset = self._paginate_params(params)

        env = request.env['tmf.trouble.ticket'].sudo()
        tickets = env.search(domain, limit=limit, offset=offset, order='id desc')
        total = env.search_count(domain)
        data = [t.to_tmf_json() for t in tickets]
        return self._json(
            self._select_fields_list(data, params.get('fields')),
            headers=[
                ("X-Total-Count", str(total)),
                ("X-Result-Count", str(len(data))),
            ],
        )

    def _create_ticket(self):
        try:
            data = self._parse_json_body()
            
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
            return self._json(new_ticket.to_tmf_json(), status=201)

        except Exception as e:
            _logger.exception("TMF621 Create Error")
            # If this still fails, it's a critical DB issue
            return self._error(400, "BAD_REQUEST", f"Creation failed: {str(e)}")

    def _patch_ticket(self, ticket):
        try:
            data = self._parse_json_body()
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

            return self._json(ticket.to_tmf_json())
        except Exception as e:
            return self._error(400, "UPDATE_ERROR", str(e))

    def _list_specifications(self, **params):
        domain = []
        if params.get('name'):
            domain.append(('name', '=', params.get('name')))
        if params.get('id'):
            domain.append(('tmf_id', '=', params.get('id')))

        limit, offset = self._paginate_params(params)

        env = request.env['tmf.trouble.ticket.specification'].sudo()
        specs = env.search(domain, limit=limit, offset=offset, order='id desc')
        total = env.search_count(domain)
        data = [s.to_tmf_json() for s in specs]
        return self._json(
            self._select_fields_list(data, params.get('fields')),
            headers=[
                ("X-Total-Count", str(total)),
                ("X-Result-Count", str(len(data))),
            ],
        )

    def _create_specification(self):
        try:
            data = self._parse_json_body()
            vals = {
                'name': data.get('name') or 'TroubleTicket',
                'description': data.get('description') or False,
                'lifecycle_status': data.get('lifecycleStatus') or 'active',
                'version': data.get('version') or '1.0',
            }
            new_spec = request.env['tmf.trouble.ticket.specification'].sudo().create(vals)
            return self._json(new_spec.to_tmf_json(), status=201)
        except Exception as e:
            _logger.exception("TMF621 TroubleTicketSpecification Create Error")
            return self._error(400, "BAD_REQUEST", f"Creation failed: {str(e)}")

    def _patch_specification(self, specification):
        try:
            data = self._parse_json_body()
            vals = {}
            if 'name' in data:
                vals['name'] = data['name']
            if 'description' in data:
                vals['description'] = data['description']
            if 'lifecycleStatus' in data:
                vals['lifecycle_status'] = data['lifecycleStatus']
            if 'version' in data:
                vals['version'] = data['version']

            if vals:
                specification.write(vals)

            return self._json(specification.to_tmf_json())
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

    def _find_specification(self, id_value):
        Specification = request.env['tmf.trouble.ticket.specification'].sudo()
        s = str(id_value)

        if s.isdigit():
            rec = Specification.browse(int(s))
            if rec.exists():
                return rec

        if 'tmf_id' in Specification._fields:
            rec = Specification.search([('tmf_id', '=', s)], limit=1)
            if rec:
                return rec

        rec = Specification.search([('name', '=', s)], limit=1)
        return rec or False
