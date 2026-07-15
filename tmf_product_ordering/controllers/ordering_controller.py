import json
import logging

from odoo import http, fields
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)


class TMFOrderingController(TMFBaseController):

    TMF_ALLOWED_STATES = {
        "acknowledged", "inProgress", "held",
        "completed", "cancelled", "rejected",
        "failed", "pending", "partial"
    }

    # ---------- helpers ----------

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

    def _update_order_from_event(self, payload, update_state=False):
        if not isinstance(payload, dict):
            return self._error(400, "InvalidRequest", "Invalid JSON body")
        event = payload.get("event") or {}
        po = event.get("productOrder") or {}
        po_id = str(po.get("id") or "").strip()
        if not po_id:
            return self._error(400, "MissingMandatoryAttribute", "event.productOrder.id is required")

        order = self._find_order(po_id)
        if not order:
            return self._error(404, "NotFound", f"ProductOrder {po_id} not found")

        vals = {}
        if update_state and po.get("state") in self.TMF_ALLOWED_STATES:
            if "tmf_status" in order._fields:
                vals["tmf_status"] = po["state"]
        if vals:
            order.sudo().write(vals)
        return self._json({}, status=201)

    # =======================================================
    # GET: List Orders
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder',
        '/tmf-api/productOrderingManagement/v5/productOrder/',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def get_orders(self, **params):
        domain = []
        limit, offset = self._paginate_params(params)

        state = params.get('state')
        if state:
            if state == "undefined" or state not in self.TMF_ALLOWED_STATES:
                return self._json([])
            if 'tmf_status' in request.env['sale.order']._fields:
                domain.append(('tmf_status', '=', state))
            else:
                return self._json([])

        orders = request.env['sale.order'].sudo().search(domain, offset=offset, limit=limit, order='id desc')
        data = self._select_fields_list([o.to_tmf_json() for o in orders], params.get('fields'))
        total = request.env['sale.order'].sudo().search_count(domain)
        return self._json(
            data,
            headers=[
                ("X-Total-Count", str(total)),
                ("X-Result-Count", str(len(data))),
            ],
        )

    # =======================================================
    # POST: Create Order
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder',
        '/tmf-api/productOrderingManagement/v5/productOrder/',
    ], type='http', auth='public', methods=['POST'], csrf=False)
    def create_order(self, **params):
        try:
            body = self._parse_json_body()
            if not isinstance(body, dict):
                return self._error(400, "InvalidRequest", "Invalid JSON body")

            # Idempotency: if externalId is provided and an order already exists,
            # return the existing one with 200 instead of creating a duplicate.
            external_id = body.get('externalId')
            if external_id:
                existing = request.env['sale.order'].sudo().search(
                    [('external_id', '=', str(external_id))], limit=1,
                )
                if existing:
                    payload = existing.to_tmf_json()
                    location = self._absolute_location(payload.get('href'), fallback_id=existing.id)
                    return self._json(payload, status=200, headers=[('Location', location)])

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
                return self._error(500, "InternalError", "No partner available to create the order")

            # TMF645 credit-block enforcement
            if 'credit_blocked' in partner._fields and partner.credit_blocked:
                return self._error(422, "CREDIT_BLOCK_ACTIVE",
                                   f"Party {partner.id} is credit-blocked")

            # Relocation feasibility pre-flight: reject before order creation.
            for _item in (body.get('productOrderItem') or []):
                if (_item.get('action') or 'add').lower() == 'modify' and 'place' in _item:
                    _tref = (_item.get('product') or {}).get('id')
                    if _tref:
                        Service = request.env['tmf.service'].sudo()
                        _svc = Service.search([('tmf_id', '=', str(_tref))], limit=1) \
                            or (Service.browse(int(_tref)) if str(_tref).isdigit() else Service.browse())
                        if _svc and _svc.exists():
                            feas = getattr(_svc, 'relocation_feasibility', 'allowed') or 'allowed'
                            if feas == 'denied':
                                return self._error(
                                    422, "Unprocessable Entity",
                                    f"Relocation feasibility denied for service {_tref}"
                                )

            order_vals = {
                'partner_id': partner.id,
                'description': body.get('description') or (quote.description if quote else 'Order via TMF API'),
            }
            if external_id:
                order_vals['external_id'] = str(external_id)
            order = request.env['sale.order'].sudo().create(order_vals)

            if quote and hasattr(quote, "sale_order_id"):
                quote.sudo().write({"sale_order_id": order.id})

            items = body.get('productOrderItem') or [{}]

            # Always ensure we have a valid Odoo product.product to create sale lines
            _fallback_tmf_prod, fallback_odoo_prod = self._get_fallback_product()

            for item in items:
                action = (item.get('action') or 'add').lower()

                # ---- modify: change an existing service's offering ----
                if action == 'modify':
                    target_ref = item.get('product') or {}
                    target_id = target_ref.get('id')
                    new_offering = item.get('productOffering') or {}
                    new_offering_id = new_offering.get('id')
                    if not target_id:
                        _logger.warning("TMF622 modify: missing product.id on item")
                        continue
                    Service = request.env['tmf.service'].sudo()
                    svc = Service.search([('tmf_id', '=', str(target_id))], limit=1) \
                        or (Service.browse(int(target_id))
                            if str(target_id).isdigit() else Service)
                    if not svc:
                        _logger.warning("TMF622 modify: service %s not found", target_id)
                        continue
                    if new_offering_id:
                        ProdSpec = request.env['tmf.product.specification'].sudo()
                        new_spec = ProdSpec.search(
                            [('tmf_id', '=', str(new_offering_id))], limit=1
                        ) or (ProdSpec.browse(int(new_offering_id))
                              if str(new_offering_id).isdigit() else ProdSpec)
                        if new_spec:
                            svc.write({'product_specification_id': new_spec.id})
                    # Device exchange: swap supportingResource on the service.
                    if 'supportingResource' in item:
                        sr_list = item.get('supportingResource') or []
                        if sr_list:
                            new_rid = str((sr_list[0] or {}).get('id') or '').strip()
                            if new_rid:
                                Lot = request.env['stock.lot'].sudo()
                                new_lot = Lot.search([('tmf_id', '=', new_rid)], limit=1) \
                                    or (Lot.browse(int(new_rid)) if new_rid.isdigit() else Lot.browse())
                                if new_lot and new_lot.exists():
                                    old_lot = svc.resource_id
                                    svc.write({'resource_id': new_lot.id})
                                    # Release old lot back to available
                                    if old_lot and old_lot.exists() and 'resource_status' in old_lot._fields:
                                        try:
                                            old_lot.write({'resource_status': 'available'})
                                        except Exception:
                                            pass
                                    # Claim new lot
                                    if 'resource_status' in new_lot._fields:
                                        try:
                                            new_lot.write({'resource_status': 'reserved'})
                                        except Exception:
                                            pass
                                    # Warranty check: if warranty expired (or absent), add fee line
                                    from odoo import fields as _fields
                                    warranty = getattr(new_lot, 'warranty_end_date', None)
                                    in_warranty = warranty and warranty >= _fields.Date.today()
                                    if not in_warranty:
                                        fee_prod = fallback_odoo_prod
                                        SOL = request.env['sale.order.line'].sudo()
                                        fee_vals = {
                                            'order_id': order.id,
                                            'product_id': fee_prod.id,
                                            'product_uom_qty': 1,
                                            'name': '[exchange-fee] out-of-warranty device swap',
                                        }
                                        if 'price_unit' in SOL._fields:
                                            fee_vals['price_unit'] = getattr(fee_prod, 'list_price', 50.0) or 50.0
                                        SOL.create(fee_vals)
                        else:
                            # Empty list = detach resource
                            old_lot = svc.resource_id
                            svc.write({'resource_id': False})
                            if old_lot and old_lot.exists() and 'resource_status' in old_lot._fields:
                                try:
                                    old_lot.write({'resource_status': 'available'})
                                except Exception:
                                    pass

                    # Owner transfer: update service partner_id when relatedParty changes.
                    if 'relatedParty' in item:
                        rp_list = item.get('relatedParty') or []
                        if rp_list:
                            new_pid = str((rp_list[0] or {}).get('id') or '').strip()
                            if new_pid:
                                Partner = request.env['res.partner'].sudo()
                                new_partner = Partner.search([('tmf_id', '=', new_pid)], limit=1) \
                                    or (Partner.browse(int(new_pid)) if new_pid.isdigit() else Partner.browse())
                                if new_partner and new_partner.exists():
                                    svc.write({'partner_id': new_partner.id})

                    # Address change: update service place when place is in the item.
                    if 'place' in item and 'place_json' in svc._fields:
                        svc.write({'place_json': json.dumps(item.get('place') or [])})

                    # Promotion apply / swap / remove via modify order.
                    # Presence of the 'promotion' key is the signal — empty list = remove.
                    if 'promotion' in item and 'applied_promotion_tmf_id' in svc._fields:
                        promo_list = item['promotion'] or []
                        if promo_list:
                            promo_ref = promo_list[0] if isinstance(promo_list, list) else promo_list
                            promo_tmf_id = str((promo_ref or {}).get('id') or '').strip()
                            if promo_tmf_id:
                                svc.write({'applied_promotion_tmf_id': promo_tmf_id})
                        else:
                            svc.write({'applied_promotion_tmf_id': False})
                    # Drop a trace order line so billing/audit can see the modify
                    odoo_prod = self._resolve_order_line_product(item, fallback_odoo_prod)
                    SOL = request.env['sale.order.line'].sudo()
                    SOL.create({
                        'order_id': order.id,
                        'product_id': odoo_prod.id,
                        'product_uom_qty': item.get('quantity') or 1,
                        'name': f"[modify] service {target_id}",
                    })
                    continue

                # ---- delete: terminate the referenced service ----
                if action == 'delete':
                    target_ref = item.get('product') or {}
                    target_id = target_ref.get('id')
                    if not target_id:
                        _logger.warning("TMF622 delete: missing product.id on item")
                        continue
                    Service = request.env['tmf.service'].sudo()
                    svc = Service.search([('tmf_id', '=', str(target_id))], limit=1) \
                        or (Service.browse(int(target_id))
                            if str(target_id).isdigit() else Service)
                    if svc:
                        svc.write({'state': 'terminated'})
                    odoo_prod = self._resolve_order_line_product(item, fallback_odoo_prod)
                    SOL = request.env['sale.order.line'].sudo()
                    SOL.create({
                        'order_id': order.id,
                        'product_id': odoo_prod.id,
                        'product_uom_qty': item.get('quantity') or 1,
                        'name': f"[delete] service {target_id}",
                    })
                    continue

                # ---- noChange: skip silently ----
                if action == 'nochange':
                    continue

                # ---- default: action == 'add' ----
                qty = item.get('quantity') or 1
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

                # SVA: if the item carries a productRelationship isChildOf,
                # create the child service immediately linked to the parent.
                parent_service = None
                for rel in (item.get('product') or {}).get('productRelationship') or []:
                    if rel.get('relationshipType') == 'isChildOf':
                        parent_tmf_id = str(
                            (rel.get('product') or {}).get('id') or ''
                        ).strip()
                        if parent_tmf_id:
                            Svc = request.env['tmf.service'].sudo()
                            parent_service = Svc.search(
                                [('tmf_id', '=', parent_tmf_id)], limit=1
                            )
                            if not parent_service and parent_tmf_id.isdigit():
                                candidate = Svc.browse(int(parent_tmf_id))
                                parent_service = candidate if candidate.exists() else None
                        break

                if parent_service:
                    svc_vals = {
                        'name': f"{odoo_prod.name} (SVA)",
                        'partner_id': partner.id,
                        'parent_service_id': parent_service.id,
                        'state': 'active',
                        'operating_status': 'running',
                        'category': 'CFS',
                        'is_service_enabled': True,
                        'has_started': True,
                        'start_mode': '1',
                        'is_stateful': True,
                    }
                    tmpl = odoo_prod.product_tmpl_id
                    if tmpl and tmpl.product_specification_id:
                        svc_vals['product_specification_id'] = (
                            tmpl.product_specification_id.id
                        )
                    request.env['tmf.service'].sudo().create(svc_vals)

            payload = order.to_tmf_json()
            location = self._absolute_location(payload.get('href'), fallback_id=order.id)
            return self._json(payload, status=201, headers=[('Location', location)])

        except Exception as e:
            _logger.exception("TMF622 POST /productOrder failed")
            return self._error(500, "InternalError", str(e))

    # =======================================================
    # GET: Retrieve by id
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>/',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def get_order_by_id(self, id, **params):
        id = self._normalize_tmf_id(id)
        order = self._find_order(id)
        if not order:
            return self._error(404, "NotFound", f"ProductOrder {id} not found")
        data = self._select_fields(order.to_tmf_json(), params.get('fields'))
        return self._json(data)

    # =======================================================
    # PATCH / DELETE productOrder
    # =======================================================
    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>/',
    ], type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_product_order(self, id, **params):
        id = self._normalize_tmf_id(id)
        order = self._find_order(id)
        if not order:
            return self._error(404, "NotFound", f"ProductOrder {id} not found")
        try:
            body = self._parse_json_body()
            if not isinstance(body, dict):
                return self._error(400, "InvalidRequest", "Invalid JSON body")
            vals = {}
            if 'description' in body:
                vals['description'] = body['description']

            # TMF state -> Odoo sale.order transition.
            # Odoo 19 states: draft, sent, sale, cancel. No 'done' — use locked=True.
            if 'state' in body:
                target = body['state']
                if target not in order.TMF_STATE_ALLOWED:
                    return self._error(400, "InvalidRequest", f"Invalid state: {target}")
                if target == 'cancelled':
                    if order.tmf_hold:
                        order.write({'tmf_hold': False})
                    if hasattr(order, '_action_cancel'):
                        order._action_cancel()
                    else:
                        order.action_cancel()
                elif target == 'held':
                    if order.state in ('draft', 'sent'):
                        order.action_confirm()
                    order.write({'tmf_hold': True})
                elif target == 'inProgress':
                    if order.tmf_hold:
                        order.write({'tmf_hold': False})
                    if order.state in ('draft', 'sent'):
                        order.action_confirm()
                    if order.locked:
                        order.action_unlock()
                elif target == 'completed':
                    if order.tmf_hold:
                        order.write({'tmf_hold': False})
                    if order.state in ('draft', 'sent'):
                        order.action_confirm()
                    if not order.locked:
                        order.write({'locked': True})
                elif target == 'acknowledged':
                    if order.tmf_hold:
                        order.write({'tmf_hold': False})
                    if order.state == 'cancel':
                        order.action_draft()

            if vals:
                order.write(vals)
            return self._json(order.to_tmf_json())
        except Exception as e:
            return self._error(400, "InvalidRequest", str(e))

    @http.route([
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/productOrder/<string:id>/',
    ], type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_product_order(self, id, **params):
        id = self._normalize_tmf_id(id)
        order = self._find_order(id)
        if not order:
            return self._error(404, "NotFound", f"ProductOrder {id} not found")
        order.unlink()
        # 204: no content
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
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "InvalidRequest", "Invalid JSON body")

            po_ref = data.get('productOrder') or {}
            po_id = po_ref.get('id')
            if not po_id:
                return self._error(400, "MissingMandatoryAttribute", "productOrder.id is required")

            Order = request.env['sale.order'].sudo()
            order = Order.browse(int(po_id)) if str(po_id).isdigit() else Order.search([('tmf_id', '=', str(po_id))], limit=1)
            if not order:
                return self._error(404, "NotFound", f"ProductOrder {po_id} not found")

            Cancel = request.env['tmf.cancel.product.order'].sudo()
            cancel_rec = Cancel.create({
                'product_order_id': order.id,
                'cancellation_reason': data.get('cancellationReason'),
                'requested_cancellation_date': data.get('requestedCancellationDate') and fields.Datetime.from_string(data['requestedCancellationDate'].replace('Z','')) or False,
                'state': 'acknowledged',
            })

            payload = cancel_rec.to_tmf_json()
            return self._json(payload, status=201, headers=[('Location', self._absolute_location(payload.get('href')))])

        except Exception as e:
            _logger.exception("CancelProductOrder POST failed")
            return self._error(400, "InvalidRequest", str(e))

    @http.route([
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/<string:id>',
        '/tmf-api/productOrderingManagement/v5/cancelProductOrder/<string:id>/',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def get_cancel_product_orders(self, id=None, **params):
        CancelModel = request.env['tmf.cancel.product.order'].sudo()
        if id:
            id = self._normalize_tmf_id(id)
            cancel_rec = CancelModel.browse(int(id)) if id.isdigit() else CancelModel.search([('tmf_id', '=', id)], limit=1)
            if not cancel_rec or not cancel_rec.exists():
                return self._error(404, "NotFound", f"CancelProductOrder {id} not found")
            return self._json(cancel_rec.to_tmf_json())
        recs = CancelModel.search([], limit=int(params.get('limit', 20)))
        return self._json([r.to_tmf_json() for r in recs])

    @http.route('/tmf-api/productOrderingManagement/v5/hub', type='http', auth='public', methods=['POST'], csrf=False)
    def register_listener(self, **params):
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "InvalidRequest", "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return self._error(400, "MissingMandatoryAttribute", "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf622-product-order-{callback}",
            "api_name": "productOrder",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": "any",
            "content_type": "application/json",
        })
        return self._json({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}, status=201)

    @http.route('/tmf-api/productOrderingManagement/v5/hub/<string:sid>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def unregister_listener(self, sid, **params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "productOrder":
            return self._error(404, "NotFound", f"Hub subscription {sid} not found")
        rec.unlink()
        # 204: no content
        return request.make_response("", status=204)

    @http.route('/tmf-api/productOrderingManagement/v5/listener/productOrderCreateEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_order_create(self, **params):
        payload = self._parse_json_body()
        return self._update_order_from_event(payload, update_state=False)

    @http.route('/tmf-api/productOrderingManagement/v5/listener/productOrderAttributeValueChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_order_attr(self, **params):
        payload = self._parse_json_body()
        return self._update_order_from_event(payload, update_state=False)

    @http.route('/tmf-api/productOrderingManagement/v5/listener/productOrderStateChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_order_state(self, **params):
        payload = self._parse_json_body()
        return self._update_order_from_event(payload, update_state=True)

    @http.route('/tmf-api/productOrderingManagement/v5/listener/productOrderDeleteEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_order_delete(self, **params):
        payload = self._parse_json_body()
        return self._update_order_from_event(payload, update_state=False)

    @http.route('/tmf-api/productOrderingManagement/v5/listener/productOrderInformationRequiredEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_order_info_required(self, **params):
        payload = self._parse_json_body()
        return self._update_order_from_event(payload, update_state=False)
