from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class CalendarEventTMF(models.Model):
    _inherit = "calendar.event"

    tmf_appointment_id = fields.Many2one(
        "tmf.appointment", string="TMF Appointment",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_appointment(self):
        Appt = self.env["tmf.appointment"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            partner = rec.partner_ids[:1] if rec.partner_ids else self.env["res.partner"]
            vals = {
                "category": rec.categ_ids[:1].name if rec.categ_ids else "General",
                "description": rec.description or rec.name or "",
                "status": "confirmed" if rec.active else "cancelled",
                "valid_for_start": rec.start,
                "valid_for_end": rec.stop,
                "partner_id": partner.id if partner else False,
            }
            if rec.tmf_appointment_id and rec.tmf_appointment_id.exists():
                rec.tmf_appointment_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            appt = Appt.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_appointment_id": appt.id})
            if hasattr(appt, "calendar_event_id"):
                appt.with_context(skip_tmf_bridge=True).write({"calendar_event_id": rec.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_appointment()
            except Exception:
                _logger.warning("TMF bridge sync failed on calendar.event create", exc_info=True)
        return recs

    def write(self, vals):
        res = super().write(vals)
        trigger = {"name", "description", "start", "stop", "partner_ids", "categ_ids", "active"}
        if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
            try:
                self._sync_tmf_appointment()
            except Exception:
                _logger.warning("TMF bridge sync failed on calendar.event write", exc_info=True)
        return res
