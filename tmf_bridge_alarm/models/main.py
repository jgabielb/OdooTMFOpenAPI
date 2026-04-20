from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFAlarmBridge(models.Model):
    _inherit = "tmf.alarm"

    activity_id = fields.Many2one(
        "mail.activity", string="Odoo Activity",
        ondelete="set null", copy=False,
    )

    def _sync_activity(self):
        Activity = self.env["mail.activity"].sudo()
        act_type = self.env.ref("mail.mail_activity_data_todo", False)
        if not act_type:
            return
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.activity_id:
                continue
            user = self.env.user
            # Attach to res.partner (has mail.thread) via user's partner
            partner = user.partner_id
            activity = Activity.with_context(skip_tmf_bridge=True).create({
                "activity_type_id": act_type.id,
                "summary": f"Alarm: {getattr(rec, 'name', '') or rec.tmf_id}",
                "note": getattr(rec, "description", "") or "",
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "res_id": partner.id,
                "user_id": user.id,
            })
            rec.with_context(skip_tmf_bridge=True).write({"activity_id": activity.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_activity()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
