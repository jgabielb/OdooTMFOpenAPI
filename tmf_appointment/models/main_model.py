from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.appointment'
    _description = 'Appointment'
    _inherit = ['tmf.model.mixin']

    category = fields.Char(string="category", help="Business category : intervention for example or to be more precise after SalesIntervention, orderDel")
    creation_date = fields.Datetime(string="creationDate", help="Appointment creation date")
    description = fields.Char(string="description", help="Short free text describing the appointment")
    external_id = fields.Char(string="externalId", help="External reference known by the customer")
    last_update = fields.Datetime(string="lastUpdate", help="Date of last appointment update")
    attachment = fields.Char(string="attachment", help="")
    calendar_event = fields.Char(string="calendarEvent", help="A calendar event reference (CalendarEventRef). The appointment is associated with a calendar event (")
    contact_medium = fields.Char(string="contactMedium", help="")
    note = fields.Char(string="note", help="")
    related_entity = fields.Char(string="relatedEntity", help="")
    related_party = fields.Char(string="relatedParty", help="")
    related_place = fields.Char(string="relatedPlace", help="Related place defines (by reference or value) the place where the appointment will take place.")
    status = fields.Char(string="status", help="")
    valid_for = fields.Char(string="validFor", help="A time period (TimePeriod). Appointment beginning date time and end date time.")

    def _get_tmf_api_path(self):
        return "/appointmentManagement/v4/Appointment"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Appointment",
            "category": self.category,
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "externalId": self.external_id,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "attachment": self.attachment,
            "calendarEvent": self.calendar_event,
            "contactMedium": self.contact_medium,
            "note": self.note,
            "relatedEntity": self.related_entity,
            "relatedParty": self.related_party,
            "relatedPlace": self.related_place,
            "status": self.status,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('appointment', 'create', rec)
        return recs

    def write(self, vals):
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
