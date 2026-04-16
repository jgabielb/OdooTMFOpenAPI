from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFPartyInteractionBridge(models.Model):
    _inherit = "tmf.party.interaction"

    mail_message_id = fields.Many2one(
        "mail.message", string="Odoo Mail Message",
        ondelete="set null", copy=False,
    )

    def _sync_mail_message(self):
        Msg = self.env["mail.message"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.mail_message_id:
                continue
            partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else False
            msg = Msg.with_context(skip_tmf_bridge=True).create({
                "body": rec.description if hasattr(rec, "description") else f"Party Interaction {rec.tmf_id}",
                "message_type": "comment",
                "subtype_id": self.env.ref("mail.mt_note").id,
                "author_id": partner.id if partner else False,
            })
            rec.with_context(skip_tmf_bridge=True).write({"mail_message_id": msg.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_mail_message()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs
