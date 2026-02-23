from odoo import api, fields, models


class CrmLeadTMFBridge(models.Model):
    _inherit = "crm.lead"

    tmf_sales_lead_id = fields.Many2one("tmf.sales.lead", string="TMF SalesLead", copy=False, index=True, ondelete="set null")

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            recs._sync_to_tmf_sales_lead()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_bridge"):
            self._sync_to_tmf_sales_lead()
        return res

    def _derive_tmf_status(self):
        self.ensure_one()
        if getattr(self.stage_id, "is_won", False):
            return "won"
        if self.stage_id and self.stage_id.name:
            return str(self.stage_id.name).strip().lower().replace(" ", "_")
        return "new"

    def _sync_to_tmf_sales_lead(self):
        tmf_model = self.env["tmf.sales.lead"].sudo().with_context(skip_crm_sync=True)
        for lead in self:
            vals = {
                "name": lead.name or f"CRM Lead {lead.id}",
                "description": lead.description or False,
                "priority": lead.priority or False,
                "status": lead._derive_tmf_status(),
            }
            if lead.tmf_sales_lead_id:
                lead.tmf_sales_lead_id.with_context(skip_crm_sync=True).write(vals)
            else:
                vals["crm_lead_id"] = lead.id
                tmf_rec = tmf_model.create(vals)
                lead.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": tmf_rec.id})
