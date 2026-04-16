from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class StockPickingTMF(models.Model):
    _inherit = "stock.picking"

    tmf_shipment_id = fields.Many2one(
        "tmf.shipment", string="TMF Shipment",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_shipment(self):
        Shipment = self.env["tmf.shipment"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            vals = {
                "name": rec.name or "Untitled",
                "description": rec.note or "",
                "state": self._map_state_to_tmf(rec),
                "partner_id": rec.partner_id.id if rec.partner_id else False,
            }
            if rec.tmf_shipment_id and rec.tmf_shipment_id.exists():
                rec.tmf_shipment_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            shipment = Shipment.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_shipment_id": shipment.id})
            if hasattr(shipment, "picking_id"):
                shipment.with_context(skip_tmf_bridge=True).write({"picking_id": rec.id})

    @staticmethod
    def _map_state_to_tmf(rec):
        mapping = {
            "draft": "initialized",
            "waiting": "acknowledged",
            "confirmed": "acknowledged",
            "assigned": "inProgress",
            "done": "completed",
            "cancel": "cancelled",
        }
        return mapping.get(rec.state, "acknowledged")

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_shipment()
            except Exception:
                _logger.warning("TMF bridge sync failed on stock.picking create", exc_info=True)
        return recs

    def write(self, vals):
        res = super().write(vals)
        trigger = {"name", "note", "partner_id", "state"}
        if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
            try:
                self._sync_tmf_shipment()
            except Exception:
                _logger.warning("TMF bridge sync failed on stock.picking write", exc_info=True)
        return res
