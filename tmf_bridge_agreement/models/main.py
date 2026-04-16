from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class SaleOrderAgreement(models.Model):
    _inherit = "sale.order"

    tmf_agreement_id = fields.Many2one(
        "tmf.agreement", string="TMF Agreement",
        ondelete="set null", copy=False,
    )

class TMFAgreementBridge(models.Model):
    _inherit = "tmf.agreement"

    sale_order_id = fields.Many2one(
        "sale.order", string="Odoo Sale Order",
        ondelete="set null", copy=False,
    )

    def _sync_sale_order(self):
        SO = self.env["sale.order"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.sale_order_id:
                continue
            partner = rec.partner_id or self.env.ref("base.partner_admin", False)
            if not partner:
                continue
            so = SO.with_context(skip_tmf_bridge=True).create({
                "partner_id": partner.id,
                "note": rec.description or rec.name or "",
                "tmf_agreement_id": rec.id,
            })
            rec.with_context(skip_tmf_bridge=True).write({"sale_order_id": so.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_sale_order()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
