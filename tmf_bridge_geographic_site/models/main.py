from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFGeoSiteBridge(models.Model):
    _inherit = "tmf.geographic.site"

    warehouse_id = fields.Many2one(
        "stock.warehouse", string="Odoo Warehouse",
        ondelete="set null", copy=False,
    )

    def _sync_warehouse(self):
        WH = self.env["stock.warehouse"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.warehouse_id:
                continue
            name = rec.name or f"Site {rec.tmf_id}"
            code = (name[:5].upper().replace(" ", "")) or "SITE"
            existing = WH.search([("code", "=", code)], limit=1)
            if existing:
                rec.with_context(skip_tmf_bridge=True).write({"warehouse_id": existing.id})
            else:
                wh = WH.with_context(skip_tmf_bridge=True).create({
                    "name": name,
                    "code": code,
                })
                rec.with_context(skip_tmf_bridge=True).write({"warehouse_id": wh.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_warehouse()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs

class StockWarehouseTMF(models.Model):
    _inherit = "stock.warehouse"

    tmf_geographic_site_id = fields.Many2one(
        "tmf.geographic.site", string="TMF Geographic Site",
        ondelete="set null", copy=False,
    )
