from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.event'
    _description = 'Event'
    _inherit = ['tmf.model.mixin']

    correlation_id = fields.Char(string="correlationId", help="The correlation id for this event.")
    description = fields.Char(string="description", help="An explnatory of the event.")
    domain = fields.Char(string="domain", help="The domain of the event.")
    event_id = fields.Char(string="eventId", help="The identifier of the notification.")
    event_time = fields.Datetime(string="eventTime", help="Time of the event occurrence.")
    event_type = fields.Char(string="eventType", help="The type of the notification.")
    priority = fields.Char(string="priority", help="A priority.")
    time_occurred = fields.Datetime(string="timeOccurred", help="The time the event occurred.")
    title = fields.Char(string="title", help="The title of the event.")
    analytic_characteristic = fields.Char(string="analyticCharacteristic", help="")
    event = fields.Char(string="event", help="The event linked to the involved resource object")
    related_party = fields.Char(string="relatedParty", help="")
    reporting_system = fields.Char(string="reportingSystem", help="Reporting System described by EntityRef")
    source = fields.Char(string="source", help="Source Entity described by EntityRef")

    def _get_tmf_api_path(self):
        return "/eventManagement/v4/Event"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Event",
            "correlationId": self.correlation_id,
            "description": self.description,
            "domain": self.domain,
            "eventId": self.event_id,
            "eventTime": self.event_time.isoformat() if self.event_time else None,
            "eventType": self.event_type,
            "priority": self.priority,
            "timeOccurred": self.time_occurred.isoformat() if self.time_occurred else None,
            "title": self.title,
            "analyticCharacteristic": self.analytic_characteristic,
            "event": self.event,
            "relatedParty": self.related_party,
            "reportingSystem": self.reporting_system,
            "source": self.source,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('event', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('event', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='event',
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
