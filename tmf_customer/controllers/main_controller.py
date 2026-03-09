from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class TMFCustomerController(http.Controller):
    
    # -------------------------------------------------------------------------
    # GET (List)
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customers(self, **params):
        domain = []
        if params.get('name'):
            domain.append(('name', 'ilike', params['name']))
        if params.get('status'):
            domain.append(('status', '=', params['status']))

        try:
            limit = max(1, min(int(params.get('limit') or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get('offset') or 0))
        except (ValueError, TypeError):
            offset = 0

        env = request.env['tmf.customer'].sudo()
        customers = env.search(domain, limit=limit, offset=offset, order='id asc')
        total = env.search_count(domain)
        data = [c.to_tmf_json() for c in customers]

        return request.make_response(
            json.dumps(data),
            headers=[
                ('Content-Type', 'application/json'),
                ('X-Total-Count', str(total)),
                ('X-Result-Count', str(len(data))),
            ]
        )

    # -------------------------------------------------------------------------
    # GET (One)
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer(self, tmf_id, **params):
        customer = request.env['tmf.customer'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        
        if not customer:
            return request.make_response(
                json.dumps({'code': '404', 'reason': 'Not Found', 'message': f'Customer {tmf_id} not found'}),
                status=404,
                headers=[('Content-Type', 'application/json')]
            )

        return request.make_response(
            json.dumps(customer.to_tmf_json()),
            headers=[('Content-Type', 'application/json')]
        )

    # -------------------------------------------------------------------------
    # POST (Create)
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer', type='http', auth='public', methods=['POST'], csrf=False)
    def create_customer(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            if not isinstance(data, dict):
                return request.make_response(
                    json.dumps({'code': 400, 'reason': 'Bad Request', 'message': 'Payload must be a JSON object'}),
                    status=400,
                    headers=[('Content-Type', 'application/json')]
                )

            # TMF629 v5 FVO minimum set
            if not data.get("name"):
                return request.make_response(
                    json.dumps({'code': 400, 'reason': 'Bad Request', 'message': "Missing mandatory field: name"}),
                    status=400,
                    headers=[('Content-Type', 'application/json')]
                )
            if not data.get("engagedParty"):
                return request.make_response(
                    json.dumps({'code': 400, 'reason': 'Bad Request', 'message': "Missing mandatory field: engagedParty"}),
                    status=400,
                    headers=[('Content-Type', 'application/json')]
                )
             
            # 1. Delegate Logic to Model (We wrote this helper in the previous step)
            vals = request.env['tmf.customer'].sudo().map_tmf_to_odoo(data)
             
            # 2. Handle Mandatory Partner creation if missing
            if 'partner_id' not in vals:
                # Basic logic: create a partner if we don't have one linked
                ep = data.get("engagedParty") or {}
                partner_name = ep.get("name") or vals.get('name') or data.get("name") or 'New TMF Customer'
                new_partner = request.env['res.partner'].sudo().create({'name': partner_name})
                vals['partner_id'] = new_partner.id

            # 3. Create (Triggers Notification automatically via Model)
            new_rec = request.env['tmf.customer'].sudo().create(vals)
            
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                status=201,
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.exception("TMF Create Error")
            return request.make_response(json.dumps({'code': 500, 'message': str(e)}), status=500)

    # -------------------------------------------------------------------------
    # PATCH (Update)
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer/<string:tmf_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def update_customer(self, tmf_id, **params):
        try:
            customer = request.env['tmf.customer'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
            if not customer:
                return request.make_response(
                    json.dumps({'code': '404', 'reason': 'Not Found', 'message': f'Customer {tmf_id} not found'}),
                    status=404,
                    headers=[('Content-Type', 'application/json')]
                )

            data = json.loads(request.httprequest.data)
            vals = request.env['tmf.customer'].sudo().map_tmf_to_odoo(data)
            
            # Write (Triggers Notification automatically via Model)
            customer.write(vals)

            return request.make_response(
                json.dumps(customer.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.exception("TMF629 PATCH customer/%s failed", tmf_id)
            return request.make_response(
                json.dumps({'code': '500', 'reason': 'Internal Server Error', 'message': str(e)}),
                status=500,
                headers=[('Content-Type', 'application/json')]
            )

    # -------------------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer/<string:tmf_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_customer(self, tmf_id, **params):
        customer = request.env['tmf.customer'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if customer:
            customer.unlink() # Triggers Notification automatically via Model
        return request.make_response('', status=204)
