from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFResourceSpecBridge(models.Model):
    _inherit = "tmf.resource.specification"

    product_tmpl_id = fields.Many2one(
        "product.template", string="Odoo Product Template",
        ondelete="set null", copy=False,
    )

    def _sync_product_template(self):
        PT = self.env["product.template"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.product_tmpl_id:
                continue
            tmpl = PT.with_context(skip_tmf_bridge=True).create({
                "name": rec.name or f"Resource Spec {rec.tmf_id}",
                "type": "consu",
            })
            rec.with_context(skip_tmf_bridge=True).write({"product_tmpl_id": tmpl.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_product_template()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
