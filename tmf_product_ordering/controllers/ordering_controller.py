from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class TMFOrderingController(http.Controller):

    TMF_ALLOWED_STATES = {
        "acknowledged", "inProgress", "held",
        "completed", "cancelled", "rejected",
        "failed", "pending", "partial"
    }

    # ---------- helpers ----------

    def _response(self, data, status=200, extra_headers=None, default_type="ProductOrder"):
        if isinstance(data, dict) and '@type' not in data:
            data['@type'] = default_type
        elif isinstance(data, list):
            for d in data:
                if isinstance(d, dict) and '@type' not in d:
                    d['@type'] = default_type

        headers = [('Content-Type', 'application/json')]
        if extra_headers:
            headers += extra_headers
        return request.make_response(json.dumps(data), headers=headers, status=status)

    def _error(self, code, reason, message):
        return self._response(
            {"code": str(code), "reason": reason, "message": message, "status": str(code), "@type": "Error"},
            status=code,
            default_type="Error",
        )

    def _filter_fields(self, data, fields_param):
        if not fields_param:
            return data

        requested = [f.strip() for f in fields_param.split(',') if f.strip()]
        mandatory = ['id', 'href', '@type']

        def filter_one(d):
            if not isinstance(d, dict):
                return d
            out = {}
            for k in mandatory:
                if k in d:
                    out[k] = d[k]
            if '@referredType' in d:
                out['@referredType'] = d['@referredType']
            for k in requested:
                out[k] = d.get(k, None)
            return out

        if isinstance(data, list):
            return [filter_one(x) for x in data]
        return filter_one(data)

    def _find_order(self, id_value):
        Order = request.env['sale.order'].sudo()
        s = str(id_value)

        if s.isdigit():
            rec = Order.browse(int(s))
            if rec.exists():
                return rec

        if 'tmf_id' in Order._fields:
            rec = Order.search([('tmf_id', '=', s)], limit=1)
            if rec:
                return rec

        rec = Order.search([('name', '=', s)], limit=1)
        return rec or False

    def _get_fallback_partner(self):
        try:
            return request.env.ref('base.public_partner').sudo()
        except Exception:
            return request.env['res.partner'].sudo().search([], limit=1)

    def _get_fallback_product(self):
        """
        Returns:
          (tmf_product_record, odoo_product_record)
        Requirements:
          - tmf.product model must exist
          - tmf.product should have odoo_product_id Many2one('product.product') (optional but recommended)
        """
        TmfProduct = request.env['tmf.product'].sudo()
        tmf_prod = TmfProduct.search([], limit=1)
        if not tmf_prod:
            tmf_prod = TmfProduct.create({
                "name": "CTK Fallback Product",
                "description": "Auto-created for CTK",
                "status": "active",
            })

        # Ensure linked Odoo product.product exists
        odoo_prod = False
        if 'odoo_product_id' in tmf_prod._fields and tmf_prod.odoo_product_id:
            odoo_prod = tmf_prod.odoo_product_id

        if not odoo_prod:
            tmpl = request.env['product.template'].sudo().create({
                "name": tmf_prod.name or "CTK Fallback Product",
                "type": "service",
                "list_price": 0.0,
            })
            odoo_prod = tmpl.product_variant_id

            if 'odoo_product_id' in tmf_prod._fields:
                tmf_prod.odoo_product_id = odoo_prod.id

        return tmf_prod, odoo_prod

    def _find_quote_from_body(self, body):
        quote_id = None
        quote_ref = body.get("quote")
        if isinstance(quote_ref, dict):
            quote_id = quote_ref.get("id")
        elif isinstance(quote_ref, list) and quote_ref and isinstance(quote_ref[0], dict):
            quote_id = quote_ref[0].get("id")
        elif body.get("quoteId"):
            quote_id = body.get("quoteId")

        if not quote_id:
            return False

        Quote = request.env["tmf.quote"].sudo()
        quote = Quote.search([("tmf_id", "=", str(quote_id))], limit=1)
        if not quote and str(quote_id).isdigit():
            quote = Quote.browse(int(quote_id))
        return quote if quote and quote.exists() else False

    def _resolve_order_line_product(self, item, fallback_product):
        odoo_prod = fallback_product
        if not isinstance(item, dict):
            return odoo_prod

        ProductTemplate = request.env["product.template"].sudo()
        TMFProduct = request.env["tmf.product"].sudo()

        # 1) Preferred path: ProductOfferingRef -> product.template(tmf_id) -> variant
        po = item.get("productOffering")
        po_id = po.get("id") if isinstance(po, dict) else None
        if po_id:
            tmpl = ProductTemplate.search([("tmf_id", "=", str(po_id))], limit=1)
            if not tmpl and str(po_id).isdigit():
                tmpl = ProductTemplate.browse(int(po_id))
            if tmpl and tmpl.exists() and tmpl.product_variant_id:
                return tmpl.product_variant_id

        # 2) Secondary path: ProductRefOrValue -> tmf.product(tmf_id) -> linked odoo product
        prod = item.get("product")
        prod_id = prod.get("id") if isinstance(prod, dict) else None
        if prod_id:
            tmf_prod = TMFProduct.search([("tmf_id", "=", str(prod_id))], limit=1)
            if not tmf_prod and str(prod_id).isdigit():
                tmf_prod = TMFProduct.browse(int(prod_id))
            if tmf_prod and tmf_prod.exists():
                if "odoo_product_id" in tmf_prod._fields and tmf_prod.odoo_product_id:
                    return tmf_prod.odoo_product_id
                # Last chance for legacy links by name
                tmpl = ProductTemplate.search([("name", "=", tmf_prod.name)], limit=1)
                if tmpl and tmpl.exists() and tmpl.product_variant_id:
                    return tmpl.product_variant_id

        # 3) CTK-safe fallback
        return odoo_prod

    def _absolute_location(self, href, fallback_id=None):
        base = request.httprequest.host_url.rstrip('/')
        if href:
            if href.startswith("http://") or href.startswith("https://"):
                return href
            if href.startswith("/"):
                return base + href
            return base + "/" + href
        if fallback_id is not None:
            return f"{base}/tmf-api/productOrderingManagement/v5/productOrder/{fallback_id}"
        return base

    # =======================================================
    # GET: List Orders
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder',
        '/tmf-api/productOrderingManagement/v5/productOrder/',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def get_orders(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 20))
        domain = []

        state = params.get('state')
        if state:
            if state == "undefined" or state not in self.TMF_ALLOWED_STATES:
                return self._response([])
            if 'tmf_status' in request.env['sale.order']._fields:
                domain.append(('tmf_status', '=', state))
            else:
                return self._response([])

        orders = request.env['sale.order'].sudo().search(domain, offset=offset, limit=limit, order='id desc')
        data = [o.to_tmf_json() for o in orders]
        data = self._filter_fields(data, params.get('fields'))
        return self._response(data)

    # =======================================================
    # POST: Create Order
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder',
        '/tmf-api/productOrderingManagement/v5/productOrder/',
    ], type='http', auth='public', methods=['POST'], csrf=False)
    def create_order(self, **params):
        try:
            body = json.loads(request.httprequest.data or b"{}")
            quote = self._find_quote_from_body(body)

            partner = None
            for party in body.get('relatedParty', []) or []:
                if party.get('role') == 'Customer' and party.get('id'):
                    Partner = request.env['res.partner'].sudo()
                    if 'tmf_id' in Partner._fields:
                        partner = Partner.search([('tmf_id', '=', str(party['id']))], limit=1)
                    break

            if not partner and quote and quote.partner_id:
                partner = quote.partner_id
            if not partner:
                partner = self._get_fallback_partner()
            if not partner:
                return self._error(500, "NO_PARTNER", "No partner available to create the order")

            order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'description': body.get('description') or (quote.description if quote else 'Order via TMF API'),
            })

            if quote and hasattr(quote, "sale_order_id"):
                quote.sudo().write({"sale_order_id": order.id})

            items = body.get('productOrderItem') or [{}]

            # Always ensure we have a valid Odoo product.product to create sale lines
            _fallback_tmf_prod, fallback_odoo_prod = self._get_fallback_product()

            for item in items:
                qty = item.get('quantity') or 1

                # For now: use fallback Odoo product (CTK doesn’t require real catalog mapping)
                odoo_prod = self._resolve_order_line_product(item, fallback_odoo_prod)

                SOL = request.env['sale.order.line'].sudo()
                vals = {
                    'order_id': order.id,
                    'product_id': odoo_prod.id,  # MUST be product.product
                    'product_uom_qty': qty,
                }

                if 'name' in SOL._fields and not vals.get('name'):
                    vals['name'] = odoo_prod.display_name

                if 'product_uom_id' in SOL._fields:
                    vals['product_uom_id'] = odoo_prod.uom_id.id
                elif 'product_uom' in SOL._fields:
                    vals['product_uom'] = odoo_prod.uom_id.id

                if 'price_unit' in SOL._fields and 'price_unit' not in vals:
                    vals['price_unit'] = getattr(odoo_prod, 'list_price', 0.0) or 0.0

                SOL.create(vals)

            payload = order.to_tmf_json()
            location = self._absolute_location(payload.get('href'), fallback_id=order.id)
            return self._response(payload, status=201, extra_headers=[('Location', location)])

        except Exception as e:
            _logger.exception("TMF622 POST /productOrder failed")
            return self._error(500, "Internal Server Error", str(e))

    # =======================================================
    # GET: Retrieve by id
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>/',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def get_order_by_id(self, id, **params):
        order = self._find_order(id)
        if not order:
            return self._error(404, "NOT_FOUND", f"ProductOrder {id} not found")
        data = self._filter_fields(order.to_tmf_json(), params.get('fields'))
        return self._response(data)

    # =======================================================
    # PATCH / DELETE productOrder
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>/',
    ], type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_product_order(self, id, **params):
        order = self._find_order(id)
        if not order:
            return self._error(404, "NOT_FOUND", f"ProductOrder {id} not found")
        try:
            body = json.loads(request.httprequest.data or b"{}")
            vals = {}
            if 'description' in body:
                vals['description'] = body['description']
            if vals:
                order.write(vals)
            return self._response(order.to_tmf_json())
        except Exception as e:
            return self._error(400, "BAD_REQUEST", str(e))

    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>/',
    ], type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_product_order(self, id, **params):
        order = self._find_order(id)
        if not order:
            return self._error(404, "NOT_FOUND", f"ProductOrder {id} not found")
        order.unlink()
        return request.make_response('', status=204)

    # =======================================================
    # cancelProductOrder (POST + GET collection/item)
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/',
    ], type='http', auth='public', methods=['POST'], csrf=False)
    def cancel_product_order_collection(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")

            po_ref = data.get('productOrder') or {}
            po_id = po_ref.get('id')
            if not po_id:
                return self._error(400, "BAD_REQUEST", "productOrder.id is required")

            Order = request.env['sale.order'].sudo()
            order = Order.browse(int(po_id)) if str(po_id).isdigit() else Order.search([('tmf_id', '=', str(po_id))], limit=1)
            if not order:
                return self._error(404, "NOT_FOUND", f"ProductOrder {po_id} not found")

            Cancel = request.env['tmf.cancel.product.order'].sudo()
            cancel_rec = Cancel.create({
                'product_order_id': order.id,
                'cancellation_reason': data.get('cancellationReason'),
                'requested_cancellation_date': data.get('requestedCancellationDate') and fields.Datetime.from_string(data['requestedCancellationDate'].replace('Z','')) or False,
                'state': 'acknowledged',
            })

            payload = cancel_rec.to_tmf_json()
            return self._response(payload, status=201, extra_headers=[('Location', self._absolute_location(payload.get('href')))])

        except Exception as e:
            _logger.exception("CancelProductOrder POST failed")
            return self._error(400, "BAD_REQUEST", str(e))

    @http.route([
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/<string:id>/',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def get_cancel_product_orders(self, id=None, **params):
        CancelModel = request.env['tmf.cancel.product.order'].sudo()
        if id:
            cancel_rec = CancelModel.browse(int(id)) if id.isdigit() else CancelModel.search([('tmf_id', '=', id)], limit=1)
            if not cancel_rec or not cancel_rec.exists():
                return self._error(404, "NOT_FOUND", f"CancelProductOrder {id} not found")
            return self._response(cancel_rec.to_tmf_json())
        recs = CancelModel.search([], limit=int(params.get('limit', 20)))
        return self._response([r.to_tmf_json() for r in recs])
