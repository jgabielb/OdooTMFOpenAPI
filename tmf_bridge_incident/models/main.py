from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFIncidentBridge(models.Model):
    _inherit = "tmf.incident"

    helpdesk_ticket_id = fields.Many2one(
        "helpdesk.ticket", string="Odoo Helpdesk Ticket",
        ondelete="set null", copy=False,
    )

    def _sync_helpdesk_ticket(self):
        Ticket = self.env["helpdesk.ticket"].sudo()
        Team = self.env["helpdesk.team"].sudo()
        team = Team.search([], limit=1)
        if not team:
            return
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.helpdesk_ticket_id:
                continue
            partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else False
            ticket = Ticket.with_context(skip_tmf_bridge=True).create({
                "name": f"Incident {rec.name or rec.tmf_id}",
                "description": rec.description if hasattr(rec, "description") else "",
                "team_id": team.id,
                "partner_id": partner.id if partner else False,
            })
            rec.with_context(skip_tmf_bridge=True).write({"helpdesk_ticket_id": ticket.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_helpdesk_ticket()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
