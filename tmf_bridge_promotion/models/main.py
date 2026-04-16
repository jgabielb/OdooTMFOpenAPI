from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFPromotionBridge(models.Model):
    _inherit = "tmf.promotion"

    pricelist_id = fields.Many2one(
        "product.pricelist", string="Odoo Pricelist",
        ondelete="set null", copy=False,
    )

    def _sync_pricelist(self):
        PL = self.env["product.pricelist"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.pricelist_id:
                continue
            pl = PL.with_context(skip_tmf_bridge=True).create({
                "name": rec.name or f"Promotion {rec.tmf_id}",
            })
            rec.with_context(skip_tmf_bridge=True).write({"pricelist_id": pl.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_pricelist()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
