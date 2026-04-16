from odoo import api, fields, models
import json
import logging

_logger = logging.getLogger(__name__)


class MailMessageTMF(models.Model):
    _inherit = "mail.message"

    tmf_comm_message_id = fields.Many2one(
        "tmf.communication.message", string="TMF Communication Message",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_comm_message(self):
        Msg = self.env["tmf.communication.message"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            if rec.message_type not in ("email", "comment"):
                continue
            sender = {}
            if rec.author_id:
                sender = {"id": str(rec.author_id.id), "name": rec.author_id.name}
            receiver = []
            for p in rec.partner_ids:
                receiver.append({"id": str(p.id), "name": p.name})
            if not receiver:
                continue
            vals = {
                "content": rec.body or rec.subject or "",
                "message_type": "email" if rec.message_type == "email" else "sms",
                "subject": rec.subject or "",
                "sender": sender,
                "receiver": receiver,
                "partner_id": rec.author_id.id if rec.author_id else False,
                "state": "completed",
            }
            if rec.tmf_comm_message_id and rec.tmf_comm_message_id.exists():
                rec.tmf_comm_message_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            msg = Msg.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_comm_message_id": msg.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_comm_message()
            except Exception:
                _logger.warning("TMF bridge sync failed on mail.message create", exc_info=True)
        return recs
