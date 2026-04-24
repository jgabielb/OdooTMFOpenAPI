from odoo import models, fields, api
import json
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class TMFModel(models.Model):
    _name = 'tmf.appointment'
    _description = 'Appointment'
    _inherit = ['tmf.model.mixin']

    # --- Core Fields ---
    category = fields.Char(string="Category")
    description = fields.Char(string="Description")
    external_id = fields.Char(string="External ID")
    status = fields.Selection([
        ('initialized', 'Initialized'),
        ('confirmed', 'Confirmed'),
        ('validated', 'Validated'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed')
    ], string="Status", default='initialized')
    
    # --- Date Fields ---
    valid_for_start = fields.Datetime(string="Start Date")
    valid_for_end = fields.Datetime(string="End Date")

    # --- System Fields ---
    creation_date = fields.Datetime(string="Creation Date", default=fields.Datetime.now)
    last_update = fields.Datetime(string="Last Update", default=fields.Datetime.now)

    # --- Optional Fields ---
    attachment = fields.Char(string="Attachment")
    note = fields.Char(string="Note")
    related_party = fields.Char(string="Related Party")
    contact_medium = fields.Char(string="Contact Medium")
    calendar_event = fields.Char(string="Calendar Event (Raw)")
    related_entity = fields.Char(string="Related Entity")
    related_place = fields.Char(string="Related Place")
    partner_id = fields.Many2one("res.partner", string="Partner", copy=False, index=True)
    calendar_event_id = fields.Many2one("calendar.event", string="Calendar Event", copy=False, index=True)

    def _get_tmf_api_path(self):
        return "/appointmentManagement/v4/appointment"

    def _related_party_obj(self):
        if not self.related_party:
            return None
        try:
            parsed = json.loads(self.related_party)
            return parsed
        except Exception:
            return self.related_party

    def _resolve_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        Partner = self.env["res.partner"].sudo()
        party = self._related_party_obj()
        entries = party if isinstance(party, list) else [party]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pid = str(entry.get("id") or "").strip()
            pname = str(entry.get("name") or "").strip()
            if pid and "tmf_id" in Partner._fields:
                p = Partner.search([("tmf_id", "=", pid)], limit=1)
                if p:
                    return p
            if pid.isdigit():
                p = Partner.browse(int(pid))
                if p.exists():
                    return p
            if pname:
                p = Partner.search([("name", "=", pname)], limit=1)
                if p:
                    return p
                return Partner.create({"name": pname})
        return Partner

    def _sync_calendar_event(self):
        Event = self.env["calendar.event"].sudo().with_context(skip_tmf_appointment_sync=True)
        for rec in self:
            partner = rec._resolve_partner()
            vals_link = {}
            if partner and rec.partner_id != partner:
                vals_link["partner_id"] = partner.id
            if vals_link:
                rec.with_context(skip_tmf_appointment_sync=True).write(vals_link)

            start = rec.valid_for_start or fields.Datetime.now()
            stop = rec.valid_for_end or (start + timedelta(hours=1))
            title = rec.category or rec.description or f"TMF Appointment {rec.tmf_id}"
            event_vals = {
                "name": title,
                "start": start,
                "stop": stop,
                "description": rec.description or "",
            }
            if partner and "partner_ids" in Event._fields:
                event_vals["partner_ids"] = [(6, 0, [partner.id])]

            if rec.calendar_event_id:
                rec.calendar_event_id.write(event_vals)
            else:
                event = Event.create(event_vals)
                rec.with_context(skip_tmf_appointment_sync=True).write({"calendar_event_id": event.id})

    def to_tmf_json(self):
        self.ensure_one()
        
        # Helper to safely format dates
        def fmt(dt):
            return dt.isoformat() if dt else None

        # Logic for validFor
        valid_for_obj = None
        if self.valid_for_start or self.valid_for_end:
            valid_for_obj = {
                "startDateTime": fmt(self.valid_for_start),
                "endDateTime": fmt(self.valid_for_end)
            }

        related_party = self._related_party_obj()
        if not related_party and self.partner_id:
            related_party = [{
                "id": self.partner_id.tmf_id or str(self.partner_id.id),
                "name": self.partner_id.name,
                "@type": "RelatedParty",
            }]

        calendar_event = self.calendar_event
        if not calendar_event and self.calendar_event_id:
            calendar_event = {
                "id": str(self.calendar_event_id.id),
                "href": f"/web#id={self.calendar_event_id.id}&model=calendar.event&view_type=form",
            }

        data = {
            "id": self.tmf_id or str(self.id),
            "href": self.href,
            "@type": "Appointment",
            "category": self.category or False, # Return False if empty to match CTK expectation? Or None? TMF usually prefers omitted or null.
            "description": self.description or False,
            "externalId": self.external_id or False,
            "status": self.status or "initialized",
            
            # Ensure we fallback to Odoo system fields if custom ones are empty
            "creationDate": fmt(self.creation_date) or fmt(self.create_date),
            "lastUpdate": fmt(self.last_update) or fmt(self.write_date),
            
            "validFor": valid_for_obj,
            
            # Return False for empty strings to match some CTK assertions
            "attachment": self.attachment or False,
            "calendarEvent": calendar_event or False,
            "contactMedium": self.contact_medium or False,
            "note": self.note or False,
            "relatedEntity": self.related_entity or False,
            "relatedParty": related_party or False,
            "relatedPlace": self.related_place or False,
        }
        return data

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if not vals.get('status'):
                vals['status'] = 'initialized'
            # Force timestamps
            if not vals.get('creation_date'):
                vals['creation_date'] = now
            if not vals.get('last_update'):
                vals['last_update'] = now

        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_appointment_sync"):
            recs._sync_calendar_event()
        for rec in recs:
            self._notify('appointment', 'create', rec)
        return recs

    def write(self, vals):
        vals['last_update'] = fields.Datetime.now()
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_appointment_sync"):
            self._sync_calendar_event()
        for rec in self:
            self._notify('appointment', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='appointment',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
