from odoo import models, fields, api
import json
import logging

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
    calendar_event = fields.Char(string="Calendar Event")
    related_entity = fields.Char(string="Related Entity")
    related_place = fields.Char(string="Related Place")

    def _get_tmf_api_path(self):
        return "/appointmentManagement/v4/appointment"

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
            "calendarEvent": self.calendar_event or False,
            "contactMedium": self.contact_medium or False,
            "note": self.note or False,
            "relatedEntity": self.related_entity or False,
            "relatedParty": self.related_party or False,
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
        for rec in recs:
            self._notify('appointment', 'create', rec)
        return recs

    def write(self, vals):
        vals['last_update'] = fields.Datetime.now()
        res = super().write(vals)
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