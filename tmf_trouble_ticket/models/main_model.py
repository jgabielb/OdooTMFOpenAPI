from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.trouble.ticket'
    _description = 'TroubleTicket'
    _inherit = ['tmf.model.mixin']

    creation_date = fields.Datetime(string="creationDate", help="The date on which the trouble ticket was created")
    description = fields.Char(string="description", help="Description of the trouble or issue")
    expected_resolution_date = fields.Datetime(string="expectedResolutionDate", help="The expected resolution date determined by the trouble ticket system")
    external_id = fields.Char(string="externalId", help="Additional identifier coming from an external system")
    last_update = fields.Datetime(string="lastUpdate", help="The date and time that the trouble ticked was last updated")
    name = fields.Char(string="name", help="Name of the trouble ticket, typically a short description provided by the user that create the ticke")
    priority = fields.Char(string="priority", help="The priority of the trouble ticket and how quickly the issue should be resolved. Example: Critical, ")
    requested_resolution_date = fields.Datetime(string="requestedResolutionDate", help="The resolution date requested by the user")
    resolution_date = fields.Datetime(string="resolutionDate", help="The date and time the trouble ticket was resolved")
    severity = fields.Char(string="severity", help="The severity of the issue. Indicate the implication of the issue on the expected functionality e.g. ")
    status_change_date = fields.Datetime(string="statusChangeDate", help="The date and time the status changed.")
    status_change_reason = fields.Char(string="statusChangeReason", help="The reason for changing the status")
    ticket_type = fields.Char(string="ticketType", help="represent a business type of the trouble ticket e.g. incident, complain, request")
    attachment = fields.Char(string="attachment", help="File(s) attached to the trouble ticket. e.g. pictur of broken device, scaning of a bill or charge")
    channel = fields.Char(string="channel", help="The channel that origin the trouble ticket")
    note = fields.Char(string="note", help="The note(s) that are associated to the ticket.")
    related_entity = fields.Char(string="relatedEntity", help="An entity that is related to the ticket such as a bill, a product, etc. The entity against which the")
    related_party = fields.Char(string="relatedParty", help="The related party(ies) that are associated to the ticket.")
    status = fields.Char(string="status", help="The current status of the trouble ticket")
    status_change = fields.Char(string="statusChange", help="The status change history that are associated to the ticket.Populated by the server")
    trouble_ticket_relationship = fields.Char(string="troubleTicketRelationship", help="A list of trouble ticket relationships (TroubleTicketRelationship [*]). Represents a relationship be")

    def _get_tmf_api_path(self):
        return "/trouble_ticketManagement/v4/TroubleTicket"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "TroubleTicket",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "expectedResolutionDate": self.expected_resolution_date.isoformat() if self.expected_resolution_date else None,
            "externalId": self.external_id,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "name": self.name,
            "priority": self.priority,
            "requestedResolutionDate": self.requested_resolution_date.isoformat() if self.requested_resolution_date else None,
            "resolutionDate": self.resolution_date.isoformat() if self.resolution_date else None,
            "severity": self.severity,
            "statusChangeDate": self.status_change_date.isoformat() if self.status_change_date else None,
            "statusChangeReason": self.status_change_reason,
            "ticketType": self.ticket_type,
            "attachment": self.attachment,
            "channel": self.channel,
            "note": self.note,
            "relatedEntity": self.related_entity,
            "relatedParty": self.related_party,
            "status": self.status,
            "statusChange": self.status_change,
            "troubleTicketRelationship": self.trouble_ticket_relationship,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('troubleTicket', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('troubleTicket', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',
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
