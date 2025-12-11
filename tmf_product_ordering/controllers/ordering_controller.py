from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class TMFOrderingController(http.Controller):

    # ---------- Shared error helper ----------

    def _error(self, code, reason, message):
        return request.make_response(
            json.dumps({"code": str(code), "reason": reason, "message": message}),
            status=code,
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # GET: List Orders
    # =======================================================
    @http.route(
        '/tmf-api/productOrderingManagement/v4/productOrder',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_orders(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 20))

        domain = []

        # Filter by TMF state: ?state=InProgress
        state = params.get('state')
        if state:
            domain.append(('tmf_status', '=', state))

        # Optional: filter by customer ?relatedParty.id=<tmf_id or db id>
        related_party_id = params.get('relatedParty.id')
        if related_party_id:
            domain += ['|',
                       ('partner_id.tmf_id', '=', related_party_id),
                       ('partner_id', '=', int(related_party_id)) if related_party_id.isdigit() else ('id', '=', 0)
                       ]

        orders = request.env['sale.order'].sudo().search(
            domain, offset=offset, limit=limit, order='id desc'
        )
        data = [o.to_tmf_json() for o in orders]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # POST: Create Order (TMF → Odoo)
    # =======================================================
    @http.route(
        '/tmf-api/productOrderingManagement/v4/productOrder',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def create_order(self, **kwargs):
        try:
            payload = request.jsonrequest or {}

            # 1. Find Customer (relatedParty with role = Customer)
            customer_tmf_id = None
            for party in payload.get('relatedParty', []):
                if party.get('role') == 'Customer':
                    customer_tmf_id = party.get('id')
                    break

            if not customer_tmf_id:
                return self._error(
                    400, "Missing Customer",
                    "No relatedParty with role 'Customer' found."
                )

            partner = request.env['res.partner'].sudo().search(
                [('tmf_id', '=', customer_tmf_id)],
                limit=1
            )
            if not partner:
                return self._error(
                    404, "Unknown Customer",
                    f"Customer with TMF ID {customer_tmf_id} not found."
                )

            # 2. Create Order Header
            order_vals = {
                'partner_id': partner.id,
                'description': payload.get('description', 'Order via TMF API'),
            }
            new_order = request.env['sale.order'].sudo().create(order_vals)

            # 3. Create Order Lines from productOrderItem[]
            for item in payload.get('productOrderItem', []):
                offering_id = item.get('productOffering', {}).get('id')
                qty = item.get('quantity', 1) or 1

                # Map ProductOffering (product.template.tmf_id) → product.product
                product = request.env['product.product'].sudo().search([
                    ('product_tmpl_id.tmf_id', '=', offering_id)
                ], limit=1)

                if not product:
                    # Cleanup partial order if a product is missing
                    new_order.unlink()
                    return self._error(
                        404, "Unknown Product",
                        f"Offering {offering_id} not found."
                    )

                request.env['sale.order.line'].sudo().create({
                    'order_id': new_order.id,
                    'product_id': product.id,
                    'product_uom_qty': qty,
                })

            # 4. Optionally confirm order (if you want TMF "InProgress" immediately)
            # new_order.action_confirm()

            # 5. Return full TMF representation
            return new_order.to_tmf_json()

        except Exception as e:
            _logger.exception("TMF Order Creation Failed")
            return self._error(500, "Internal Server Error", str(e))

    # =======================================================
    # GET: Retrieve Order by TMF ID
    # =======================================================
    @http.route(
        '/tmf-api/productOrderingManagement/v4/productOrder/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_order(self, tmf_id, **params):
        order = request.env['sale.order'].sudo().search(
            [('tmf_id', '=', tmf_id)], limit=1
        )
        if not order:
            return self._error(404, "Not Found", f"ProductOrder {tmf_id} not found")

        data = order.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # PATCH: Update Order (minimal)
    # =======================================================
    @http.route(
        '/tmf-api/productOrderingManagement/v4/productOrder/<string:tmf_id>',
        type='json', auth='public', methods=['PATCH'], csrf=False
    )
    def patch_order(self, tmf_id, **kwargs):
        order = request.env['sale.order'].sudo().search(
            [('tmf_id', '=', tmf_id)], limit=1
        )
        if not order:
            return self._error(404, "Not Found", f"ProductOrder {tmf_id} not found")

        payload = request.jsonrequest or {}

        # Minimal example: allow description update
        vals = {}
        if 'description' in payload:
            vals['description'] = payload['description']

        # NOTE: changing TMF state properly would require mapping to Odoo 'state'.
        # For now we avoid writing tmf_status directly because it's computed.
        if vals:
            order.sudo().write(vals)

        return order.to_tmf_json()

    # =======================================================
    # POST: cancelProductOrder
    # =======================================================
    @http.route(
        '/tmf-api/productOrderingManagement/v4/cancelProductOrder',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def cancel_product_order(self, **kwargs):
        payload = request.jsonrequest or {}
        related_order_id = payload.get("productOrder", {}).get("id")

        if not related_order_id:
            return self._error(400, "Bad Request", "productOrder.id is required")

        order = request.env['sale.order'].sudo().search(
            [('tmf_id', '=', related_order_id)], limit=1
        )
        if not order:
            return self._error(
                404, "Not Found",
                f"ProductOrder {related_order_id} not found"
            )

        # Business rule: cancel Odoo order (this sets state='cancel')
        try:
            order.action_cancel()
        except Exception as e:
            _logger.warning("Error cancelling order %s: %s", order.id, e)

        cancel_json = {
            "id": payload.get("id") or order.tmf_id or str(order.id),
            "href": f"/tmf-api/productOrderingManagement/v4/cancelProductOrder/{order.tmf_id or order.id}",
            "productOrder": {
                "id": order.tmf_id or str(order.id),
                "href": order.tmf_href,
            },
            "state": "Done",
            "@type": "CancelProductOrder",
        }
        return cancel_json

    # =======================================================
    # HUB: Event Subscriptions
    # =======================================================
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

    @http.route(
        '/tmf-api/productOrderingManagement/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_order_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
