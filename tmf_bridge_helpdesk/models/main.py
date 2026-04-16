from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTicketTMF(models.Model):
    _inherit = "helpdesk.ticket"

    tmf_trouble_ticket_id = fields.Many2one(
        "tmf.trouble.ticket", string="TMF Trouble Ticket",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_trouble_ticket(self):
        TT = self.env["tmf.trouble.ticket"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            vals = {
                "description": rec.description or rec.name or "No description",
                "severity": "Medium",
                "priority": "Medium",
                "status": self._map_stage_to_tmf(rec),
                "partner_id": rec.partner_id.id if rec.partner_id else False,
            }
            if rec.tmf_trouble_ticket_id:
                tt = rec.tmf_trouble_ticket_id
                if tt.exists():
                    tt.with_context(skip_tmf_bridge=True).write(vals)
                    continue
            vals["name"] = f"TT-HD-{rec.id}"
            tt = TT.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_trouble_ticket_id": tt.id})
            if hasattr(tt, "helpdesk_ticket_id"):
                tt.with_context(skip_tmf_bridge=True).write({"helpdesk_ticket_id": rec.id})

    @staticmethod
    def _map_stage_to_tmf(rec):
        if not rec.stage_id:
            return "Submitted"
        name = (rec.stage_id.name or "").lower()
        if "new" in name or "draft" in name:
            return "Submitted"
        if "progress" in name or "open" in name:
            return "InProgress"
        if "resolve" in name or "done" in name or "close" in name or "solved" in name:
            return "Resolved"
        if "cancel" in name:
            return "Cancelled"
        return "InProgress"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_trouble_ticket()
            except Exception:
                _logger.warning("TMF bridge sync failed on helpdesk.ticket create", exc_info=True)
        return recs

    def write(self, vals):
        res = super().write(vals)
        trigger = {"name", "description", "partner_id", "stage_id", "priority"}
        if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
            try:
                self._sync_tmf_trouble_ticket()
            except Exception:
                _logger.warning("TMF bridge sync failed on helpdesk.ticket write", exc_info=True)
        return res
