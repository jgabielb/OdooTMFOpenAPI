from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.party.role'
    _description = 'PartyRole'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="name", help="A word, term, or phrase by which the PartyRole is known and distinguished from other PartyRoles.")
    status = fields.Char(string="status", help="Used to track the lifecycle status of the party role.")
    status_reason = fields.Char(string="statusReason", help="A string providing an explanation on the value of the status lifecycle. For instance if the status i")
    account = fields.Char(string="account", help="")
    agreement = fields.Char(string="agreement", help="")
    characteristic = fields.Char(string="characteristic", help="Describes the characteristic of a party role.")
    contact_medium = fields.Char(string="contactMedium", help="")
    credit_profile = fields.Char(string="creditProfile", help="")
    engaged_party = fields.Char(string="engagedParty", help="")
    payment_method = fields.Char(string="paymentMethod", help="")
    related_party = fields.Char(string="relatedParty", help="")
    role_type = fields.Char(string="roleType", help="")
    valid_for = fields.Char(string="validFor", help="The time period that the PartyRole is valid for.")

    def _get_tmf_api_path(self):
        return "/party_roleManagement/v4/PartyRole"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "PartyRole",
            "name": self.name,
            "status": self.status,
            "statusReason": self.status_reason,
            "account": self.account,
            "agreement": self.agreement,
            "characteristic": self.characteristic,
            "contactMedium": self.contact_medium,
            "creditProfile": self.credit_profile,
            "engagedParty": self.engaged_party,
            "paymentMethod": self.payment_method,
            "relatedParty": self.related_party,
            "roleType": self.role_type,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('partyRole', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('partyRole', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='partyRole',
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
