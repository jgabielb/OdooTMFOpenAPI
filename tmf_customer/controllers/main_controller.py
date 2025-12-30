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
        # We can add filtering logic here later (e.g. ?name=John)
        customers = request.env['tmf.customer'].sudo().search([])
        
        return request.make_response(
            json.dumps([c.to_tmf_json() for c in customers]),
            headers=[('Content-Type', 'application/json')]
        )

    # -------------------------------------------------------------------------
    # GET (One)
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer(self, tmf_id, **params):
        customer = request.env['tmf.customer'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        
        if not customer:
            return request.make_response(json.dumps({'error': 'Not Found'}), status=404)

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
            
            # 1. Delegate Logic to Model (We wrote this helper in the previous step)
            vals = request.env['tmf.customer'].sudo().map_tmf_to_odoo(data)
            
            # 2. Handle Mandatory Partner creation if missing
            if 'partner_id' not in vals:
                # Basic logic: create a partner if we don't have one linked
                new_partner = request.env['res.partner'].sudo().create({'name': vals.get('name', 'New TMF Customer')})
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
                return request.make_response(json.dumps({'error': 'Not Found'}), status=404)

            data = json.loads(request.httprequest.data)
            vals = request.env['tmf.customer'].sudo().map_tmf_to_odoo(data)
            
            # Write (Triggers Notification automatically via Model)
            customer.write(vals)

            return request.make_response(
                json.dumps(customer.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'code': 500, 'message': str(e)}), status=500)

    # -------------------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------------------
    @http.route('/tmf-api/customerManagement/v5/customer/<string:tmf_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_customer(self, tmf_id, **params):
        customer = request.env['tmf.customer'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if customer:
            customer.unlink() # Triggers Notification automatically via Model
        return request.make_response('', status=204)