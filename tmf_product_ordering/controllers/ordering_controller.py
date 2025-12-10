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
        # Fetch Odoo Orders
        orders = request.env['sale.order'].sudo().search([], limit=20, order='id desc')
        
        response_data = []
        for o in orders:
            order_json = {
                "id": o.tmf_id or str(o.id),
                "href": o.href,
                "description": o.description or o.name,
                "state": o.tmf_status,
                "orderDate": o.date_order.isoformat() if o.date_order else None,
                "@type": "ProductOrder",
                
                # Link to Customer
                "relatedParty": [{
                    "id": o.partner_id.tmf_id,
                    "name": o.partner_id.name,
                    "role": "Customer"
                }],
                
                # Order Items (Lines)
                "productOrderItem": []
            }
            
            # Map Lines
            for line in o.order_line:
                order_json["productOrderItem"].append({
                    "id": line.tmf_id or str(line.id),
                    "quantity": line.product_uom_qty,
                    "productOffering": {
                        "id": line.product_template_id.tmf_id,
                        "name": line.product_template_id.name
                    },
                    "itemPrice": [{
                        "price": {
                            "value": line.price_unit,
                            "unit": o.currency_id.name
                        }
                    }]
                })

            response_data.append(order_json)

        return request.make_response(
            json.dumps(response_data),
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

    def _error(self, code, reason, message):
        return request.make_response(
            json.dumps({"code": str(code), "reason": reason, "message": message}),
            status=code,
            headers=[('Content-Type', 'application/json')]
        )