"""Bridge: crm.lead → TMF Party Interaction + Party auto-link.

When a lead/opportunity is created or updated in Odoo CRM:
1. Ensure the contact (partner) has a tmf_id (auto-assign if missing).
2. Create/update a TMF Party Interaction record to track the engagement.

This bridges the TAM Market/Sales domain so CRM activity is visible
in the TMF layer (Customer360, Party Interaction API, etc.).
"""
import uuid
from datetime import datetime, timezone

from odoo import api, fields, models


class CrmLeadBridge(models.Model):
    _inherit = "crm.lead"

    tmf_interaction_id = fields.Many2one(
        "tmf.party.interaction", string="TMF Interaction",
        copy=False, index=True, ondelete="set null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if not rec.env.context.get("skip_tmf_bridge"):
                rec._sync_to_tmf()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_bridge"):
            for rec in self:
                rec._sync_to_tmf()
        return res

    def _ensure_partner_tmf_id(self):
        """Make sure the lead's partner has a tmf_id."""
        partner = self.partner_id
        if not partner:
            return None
        if not partner.tmf_id:
            partner.with_context(skip_tmf_bridge=True).write({
                "tmf_id": str(uuid.uuid4()),
            })
        return partner

    def _lead_stage_to_status(self):
        """Map CRM stage to a TMF interaction status."""
        if self.stage_id:
            name = (self.stage_id.name or "").lower()
            if "won" in name:
                return "completed"
            if "lost" in name:
                return "failed"
            if "qualif" in name or "proposition" in name:
                return "inProgress"
        if self.type == "opportunity":
            return "inProgress"
        return "initial"

    def _sync_to_tmf(self):
        """Create or update the linked TMF Party Interaction."""
        self.ensure_one()
        partner = self._ensure_partner_tmf_id()

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        direction = "inbound" if self.type == "lead" else "outbound"
        reason = f"CRM {'Lead' if self.type == 'lead' else 'Opportunity'}"
        status = self._lead_stage_to_status()

        vals = {
            "description": self.name or "",
            "direction": direction,
            "reason": reason,
            "status": status,
            "status_change_date": fields.Datetime.now(),
            "tmf_type": "PartyInteraction",
        }

        if partner:
            vals["partner_id"] = partner.id
            vals["related_party"] = [{
                "id": str(partner.tmf_id or partner.id),
                "name": partner.name,
                "role": "Customer",
            }]
            vals["related_channel"] = [{"id": "crm", "name": "Odoo CRM"}]

        PI = self.env["tmf.party.interaction"].sudo()

        if self.tmf_interaction_id:
            self.tmf_interaction_id.with_context(skip_tmf_bridge=True).write(vals)
        else:
            vals["creation_date"] = fields.Datetime.now()
            vals["interaction_date"] = {"startDateTime": now}
            interaction = PI.with_context(skip_tmf_bridge=True).create(vals)
            self.with_context(skip_tmf_bridge=True).write({
                "tmf_interaction_id": interaction.id,
            })
