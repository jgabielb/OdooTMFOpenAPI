from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFQuoteBridge(models.Model):
    _inherit = "tmf.quote"

    sale_order_id = fields.Many2one(
        "sale.order", string="Odoo Quotation",
        ondelete="set null", copy=False,
    )

    def _sync_quotation(self):
        SO = self.env["sale.order"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.sale_order_id:
                continue
            partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else self.env.ref("base.partner_admin", False)
            if not partner:
                continue
            so = SO.with_context(skip_tmf_bridge=True).create({
                "partner_id": partner.id,
                "note": rec.description if hasattr(rec, "description") else "",
            })
            rec.with_context(skip_tmf_bridge=True).write({"sale_order_id": so.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_quotation()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
