from odoo import models, fields, api
import json


# ============================================================
# Sale Order -> TMF622 ProductOrder
# ============================================================

class SaleOrder(models.Model):
    _name = 'sale.order'  # silence Odoo 19 warning when using list _inherit
    _inherit = ['sale.order', 'tmf.model.mixin']

    TMF_STATE_ALLOWED = {
        "acknowledged", "inProgress", "held",
        "completed", "cancelled", "rejected",
        "failed", "pending", "partial"
    }

    tmf_status = fields.Selection([
        ('acknowledged', 'acknowledged'),
        ('inProgress', 'inProgress'),
        ('held', 'held'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('rejected', 'rejected'),
        ('failed', 'failed'),
        ('pending', 'pending'),
        ('partial', 'partial'),
    ], string="TMF Status", compute="_compute_tmf_status", store=True, index=True)

    description = fields.Text(string="Order Description")

    # ---------- helpers ----------

    def _tmf_state_from_odoo(self):
        self.ensure_one()
        st = self.state
        if st in ("draft", "sent"):
            return "acknowledged"
        if st == "sale":
            return "completed" if self.locked else "inProgress"
        if st == "cancel":
            return "cancelled"
        return "acknowledged"

    def _rfc3339(self, dt):
        # Always return a string (CTK expects string, not null)
        if not dt:
            dt = fields.Datetime.now()
        s = fields.Datetime.to_string(dt)  # "YYYY-MM-DD HH:MM:SS"
        return s.replace(" ", "T") + "Z"

    def _get_tmf_api_path(self):
        return "/productOrderingManagement/v5/productOrder"

    @property
    def tmf_href(self):
        # Relative href (controller should build absolute Location)
        base = "/tmf-api" + self._get_tmf_api_path()
        oid = self.tmf_id or str(self.id)
        return f"{base}/{oid}"

    # ---------- TMF JSON ----------

    def to_tmf_json(self):
        self.ensure_one()

        order_id = self.tmf_id or str(self.id)
        state = self.tmf_status or self._tmf_state_from_odoo()
        if state not in self.TMF_STATE_ALLOWED:
            state = self._tmf_state_from_odoo()

        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')

        items = []
        for line in self.order_line:
            offering_id = str(getattr(line.product_id.product_tmpl_id, 'tmf_id', None) or line.product_id.id)

            items.append({
                "id": str(getattr(line, 'tmf_id', None) or line.id),
                "action": getattr(line, 'tmf_action', None) or "add",
                "@type": "ProductOrderItem",
                "state": state,

                # IMPORTANT for CTK oneOf: make it a Product VALUE (not ProductRef)
                "product": {
                    "isBundle": False,
                    "@type": "Product",
                },

                # Keep offering ref (safe)
                "productOffering": {
                    "id": offering_id,
                    "href": f"{base}/tmf-api/productCatalogManagement/v5/productOffering/{offering_id}",
                    "@type": "ProductOfferingRef",
                    "@referredType": "ProductOffering",
                }
            })

        # CTK minItems=1
        if not items:
            items = [{
                "id": "1",
                "action": "add",
                "@type": "ProductOrderItem",
                "state": state,
                "product": {"isBundle": False, "@type": "Product"},
                "productOffering": {
                    "id": "0",
                    "href": f"{base}/tmf-api/productCatalogManagement/v5/productOffering/0",
                    "@type": "ProductOfferingRef",
                    "@referredType": "ProductOffering",
                }
            }]

        # relatedParty (keep minimal, valid)
        related_party = []
        if self.partner_id:
            related_party.append({
                "id": str(getattr(self.partner_id, 'tmf_id', None) or self.partner_id.id),
                "href": f"{base}/tmf-api/partyManagement/v5/individual/{self.partner_id.id}",
                "name": self.partner_id.name,
                "role": "Customer",
                "@type": "RelatedParty",
                "@referredType": "Individual"
            })

        return {
            "id": str(order_id),
            "href": self.tmf_href,  # relative
            "@type": "ProductOrder",
            "description": self.description or self.name or "Order",
            "state": state,
            "orderDate": self._rfc3339(self.date_order),
            "creationDate": self._rfc3339(self.create_date),
            "completionDate": self._rfc3339(self.write_date),
            "productOrderItem": items,
            "relatedParty": related_party,
        }

    # ---------- compute ----------

    @api.depends('state', 'locked')
    def _compute_tmf_status(self):
        for order in self:
            if order.state in ('draft', 'sent'):
                order.tmf_status = 'acknowledged'
            elif order.state == 'sale':
                order.tmf_status = 'completed' if order.locked else 'inProgress'
            elif order.state == 'cancel':
                order.tmf_status = 'cancelled'
            else:
                order.tmf_status = 'acknowledged'

    # ---------- notification hooks ----------

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            try:
                order.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOrder',
                    event_type='ProductOrderCreateEvent',
                    resource_json=order.to_tmf_json(),
                )
            except Exception:
                pass
        return orders

    def write(self, vals):
        old_state = {order.id: order.tmf_status for order in self}
        res = super().write(vals)
        for order in self:
            try:
                event_type = 'ProductOrderStateChangeEvent' if 'state' in vals else 'ProductOrderAttributeValueChangeEvent'
                order.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOrder',
                    event_type=event_type,
                    resource_json=order.to_tmf_json(),
                )
                if 'state' in vals and old_state.get(order.id) != order.tmf_status and order.tmf_status == 'pending':
                    order.env['tmf.hub.subscription']._notify_subscribers(
                        api_name='productOrder',
                        event_type='ProductOrderInformationRequiredEvent',
                        resource_json=order.to_tmf_json(),
                    )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [o.to_tmf_json() for o in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOrder',
                    event_type='ProductOrderDeleteEvent',
                    resource_json=payload,
                )
            except Exception:
                continue
        return res


# ============================================================
# Sale Order Line (keep mixin ids)
# ============================================================

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'  # silence warning
    _inherit = ['sale.order.line', 'tmf.model.mixin']

    def _get_tmf_api_path(self):
        return ""


# ============================================================
# TMF622 CancelProductOrder
# ============================================================

class CancelProductOrder(models.Model):
    _name = 'tmf.cancel.product.order'
    _description = 'TMF Cancel Product Order'
    _inherit = ['tmf.model.mixin']

    product_order_id = fields.Many2one('sale.order', required=True)
    cancellation_reason = fields.Char()
    effective_cancellation_date = fields.Datetime()
    requested_cancellation_date = fields.Datetime()
    state = fields.Char(default='acknowledged', index=True)
    error = fields.Char()

    def _get_tmf_api_path(self):
        return "/productOrderingManagement/v5/cancelProductOrder"

    @property
    def tmf_href(self):
        base = "/tmf-api" + self._get_tmf_api_path()
        cid = self.tmf_id or str(self.id)
        return f"{base}/{cid}"

    def to_tmf_json(self):
        self.ensure_one()

        data = {
            "id": str(self.tmf_id or self.id),
            "href": self.tmf_href,
            "@type": "CancelProductOrder",
            "state": self.state,
            "productOrder": {
                "id": str(self.product_order_id.tmf_id or self.product_order_id.id),
                "@type": "ProductOrderRef",
                "@referredType": "ProductOrder",
                "href": f"/tmf-api/productOrderingManagement/v5/productOrder/{self.product_order_id.tmf_id or self.product_order_id.id}",
            },
        }

        if self.cancellation_reason:
            data["cancellationReason"] = self.cancellation_reason
        if self.effective_cancellation_date:
            data["effectiveCancellationDate"] = self.effective_cancellation_date.isoformat() + "Z"
        if self.requested_cancellation_date:
            data["requestedCancellationDate"] = self.requested_cancellation_date.isoformat() + "Z"
        if self.error:
            data["error"] = self.error

        return data
