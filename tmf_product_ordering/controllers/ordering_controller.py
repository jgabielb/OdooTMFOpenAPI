from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class TMFOrderingController(http.Controller):

    # =======================================================
    # GET: List Orders
    # =======================================================
    @http.route('/tmf-api/productOrderingManagement/v4/productOrder', type='http', auth='public', methods=['GET'], csrf=False)
    def get_orders(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 20))

        domain = []
        state = params.get('state')
        if state:
            domain.append(('tmf_status', '=', state))

        orders = request.env['sale.order'].sudo().search(domain, offset=offset, limit=limit, order='id desc')
        data = [o.to_tmf_json() for o in orders]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # POST: Create Order (The "Magic" Part)
    # =======================================================
    @http.route('/tmf-api/productOrderingManagement/v4/productOrder', type='http', auth='public', methods=['POST'], csrf=False)
    def create_order(self, **params):
        try:
            # 1. Parse JSON Body
            data = json.loads(request.httprequest.data)
            
            # 2. Find Customer (By TMF ID)
            # We look for the party with role 'Customer'
            customer_tmf_id = None
            for party in data.get('relatedParty', []):
                if party.get('role') == 'Customer':
                    customer_tmf_id = party.get('id')
                    break
            
            if not customer_tmf_id:
                return self._error(400, "Missing Customer", "No relatedParty with role 'Customer' found.")

            partner = request.env['res.partner'].sudo().search([('tmf_id', '=', customer_tmf_id)], limit=1)
            if not partner:
                return self._error(404, "Unknown Customer", f"Customer with ID {customer_tmf_id} not found.")

            # 3. Create the Order Header
            order_vals = {
                'partner_id': partner.id,
                'description': data.get('description', 'Order via TMF API')
            }
            new_order = request.env['sale.order'].sudo().create(order_vals)

            # 4. Create Order Lines
            for item in data.get('productOrderItem', []):
                offering_id = item.get('productOffering', {}).get('id')
                qty = item.get('quantity', 1)

                # Find Product Variant
                # TMF sends Offering ID (Template), Odoo needs Product ID (Variant)
                # We pick the first variant found for that template
                product = request.env['product.product'].sudo().search([
                    ('product_tmpl_id.tmf_id', '=', offering_id)
                ], limit=1)

                if not product:
                    # Cleanup: Delete the partial order if a product is missing (Transaction atomic-ish)
                    new_order.unlink()
                    return self._error(404, "Unknown Product", f"Offering {offering_id} not found.")

                request.env['sale.order.line'].sudo().create({
                    'order_id': new_order.id,
                    'product_id': product.id,
                    'product_uom_qty': qty
                })

            # 5. Confirm Order (Optional - TMF usually expects 'Acknowledged' which is Draft)
            # new_order.action_confirm() 

            # 6. Return the created object
            response = {
                "id": new_order.tmf_id,
                "href": new_order.href,
                "state": "Acknowledged",
                "@type": "ProductOrder"
            }
            return request.make_response(json.dumps(response), status=201, headers=[('Content-Type', 'application/json')])

        except Exception as e:
            _logger.exception("TMF Order Creation Failed")
            return self._error(500, "Internal Server Error", str(e))

    @http.route(
        '/tmf-api/productOrderingManagement/v4/productOrder/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_order(self, tmf_id, **params):
        order = request.env['sale.order'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not order:
            return self._error(404, "Not Found", f"ProductOrder {tmf_id} not found")

        data = order.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )
    
    @http.route(
        '/tmf-api/productOrderingManagement/v4/productOrder/<string:tmf_id>',
        type='json', auth='public', methods=['PATCH'], csrf=False
    )
    def patch_order(self, tmf_id, **kwargs):
        order = request.env['sale.order'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not order:
            return self._error(404, "Not Found", f"ProductOrder {tmf_id} not found")

        payload = request.jsonrequest or {}

        # Minimal example: only update tmf_status
        new_state = payload.get("state")
        if new_state:
            order.tmf_status = new_state

        return order.to_tmf_json()
    
    @http.route(
        '/tmf-api/productOrderingManagement/v4/cancelProductOrder',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def cancel_product_order(self, **kwargs):
        payload = request.jsonrequest or {}
        related_order_id = payload.get("productOrder", {}).get("id")

        if not related_order_id:
            return self._error(400, "Bad Request", "productOrder.id is required")

        order = request.env['sale.order'].sudo().search([('tmf_id', '=', related_order_id)], limit=1)
        if not order:
            return self._error(404, "Not Found", f"ProductOrder {related_order_id} not found")

        # Business rule: mark as cancelled + cancel in Odoo
        order.action_cancel()
        order.tmf_status = "Cancelled"

        # Response should be a CancelProductOrder according to TMF622
        cancel_json = {
            "id": payload.get("id") or order.tmf_id,
            "href": f"/tmf-api/productOrderingManagement/v4/cancelProductOrder/{order.tmf_id}",
            "productOrder": {
                "id": order.tmf_id,
                "href": order.tmf_href
            },
            "state": "Done",
            "@type": "CancelProductOrder"
        }
        return cancel_json

    @http.route(
        '/tmf-api/productOrderingManagement/v4/hub',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_order_events(self, **kwargs):
        """Create subscription for ProductOrder events"""
        payload = request.jsonrequest or {}

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        sub = request.env['tmf.hub.subscription'].sudo().create({
            "api_name": "productOrder",
            "callback": callback,
            "query": query,
        })

        return {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query,
            "@type": "EventSubscription"
        }

    @http.route(
        '/tmf-api/productOrderingManagement/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_order_events(self, sub_id, **kwargs):
        """Delete subscription"""
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
    
    @http.route(
        '/tmf-api/productOrderingManagement/v4/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_order_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'productOrder')
        ])
        data = [{
            "id": str(s.id),
            "callback": s.callback,
            "query": s.query,
            "@type": "EventSubscription"
        } for s in subs]
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )
    
    def _error(self, code, reason, message):
        return request.make_response(
            json.dumps({"code": str(code), "reason": reason, "message": message}),
            status=code,
            headers=[('Content-Type', 'application/json')]
        )