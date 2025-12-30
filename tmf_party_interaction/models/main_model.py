from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.party.interaction'
    _description = 'PartyInteraction'
    _inherit = ['tmf.model.mixin']

    creation_date = fields.Datetime(string="creationDate", help="Date when the interaction is created in the system")
    description = fields.Char(string="description", help="Description of the interaction")
    direction = fields.Char(string="direction", help="Specifies who started the interaction. It might be the party or the enterprise exposing this API. Po")
    reason = fields.Char(string="reason", help="Reason why the interaction happened")
    status = fields.Char(string="status", help="Status of the interaction (opened, inProgress, completed)")
    status_change_date = fields.Datetime(string="statusChangeDate", help="Last time the status changed")
    attachment = fields.Char(string="attachment", help="")
    channel = fields.Char(string="channel", help="Where the interaction took place (e.g. web, mobile app, store, kiosk, etc.)")
    interaction_date = fields.Char(string="interactionDate", help="The period during which the interaction took place. Start and end will be different in case of a cal")
    interaction_item = fields.Char(string="interactionItem", help="")
    interaction_relationship = fields.Char(string="interactionRelationship", help="")
    note = fields.Char(string="note", help="")
    related_party = fields.Char(string="relatedParty", help="")

    def _get_tmf_api_path(self):
        return "/party_interactionManagement/v4/PartyInteraction"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "PartyInteraction",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "direction": self.direction,
            "reason": self.reason,
            "status": self.status,
            "statusChangeDate": self.status_change_date.isoformat() if self.status_change_date else None,
            "attachment": self.attachment,
            "channel": self.channel,
            "interactionDate": self.interaction_date,
            "interactionItem": self.interaction_item,
            "interactionRelationship": self.interaction_relationship,
            "note": self.note,
            "relatedParty": self.related_party,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('partyInteraction', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('partyInteraction', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='partyInteraction',
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
