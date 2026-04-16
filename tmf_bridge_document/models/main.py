from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class TMFDocumentBridge(models.Model):
    _inherit = "tmf.document"

    attachment_id = fields.Many2one(
        "ir.attachment", string="Odoo Attachment",
        ondelete="set null", copy=False,
    )

    def _sync_attachment(self):
        Att = self.env["ir.attachment"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge") or rec.attachment_id:
                continue
            att = Att.with_context(skip_tmf_bridge=True).create({
                "name": rec.name or f"TMF Document {rec.tmf_id}",
                "type": "url",
                "url": rec.href if hasattr(rec, "href") else "",
            })
            rec.with_context(skip_tmf_bridge=True).write({"attachment_id": att.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_attachment()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs

class IrAttachmentTMF(models.Model):
    _inherit = "ir.attachment"

    tmf_document_id = fields.Many2one(
        "tmf.document", string="TMF Document",
        ondelete="set null", copy=False,
    )
