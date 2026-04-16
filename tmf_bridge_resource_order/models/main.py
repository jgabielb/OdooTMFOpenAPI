from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFResourceOrderBridge(models.Model):
    _inherit = "tmf.resource.order"

    purchase_order_id = fields.Many2one(
        "purchase.order", string="Odoo Purchase Order",
        ondelete="set null", copy=False,
    )

    def _sync_purchase_order(self):
        PO = self.env["purchase.order"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.purchase_order_id:
                continue
            partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else self.env.ref("base.partner_admin", False)
            if not partner:
                continue
            po = PO.with_context(skip_tmf_bridge=True).create({
                "partner_id": partner.id,
                "notes": f"TMF Resource Order {rec.tmf_id}",
            })
            rec.with_context(skip_tmf_bridge=True).write({"purchase_order_id": po.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_purchase_order()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
