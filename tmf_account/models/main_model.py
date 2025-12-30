from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.account'
    _description = 'Account'
    _inherit = ['tmf.model.mixin']

    account_type = fields.Char(string="accountType", help="A categorization of an account, such as individual, joint, and so forth, whose instances share some ")
    description = fields.Char(string="description", help="Detailed description of the party account")
    last_modified = fields.Datetime(string="lastModified", help="Date of last modification of the account")
    name = fields.Char(string="name", help="Name of the account")
    state = fields.Char(string="state", help="Contains the lifecycle state such as: Active, Closed, Suspended and so on.")
    account_balance = fields.Char(string="accountBalance", help="")
    account_relationship = fields.Char(string="accountRelationship", help="")
    contact = fields.Char(string="contact", help="")
    credit_limit = fields.Char(string="creditLimit", help="The maximum amount of money that may be charged on an account")
    related_party = fields.Char(string="relatedParty", help="")
    tax_exemption = fields.Char(string="taxExemption", help="")

    def _get_tmf_api_path(self):
        return "/accountManagement/v4/Account"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Account",
            "accountType": self.account_type,
            "description": self.description,
            "lastModified": self.last_modified.isoformat() if self.last_modified else None,
            "name": self.name,
            "state": self.state,
            "accountBalance": self.account_balance,
            "accountRelationship": self.account_relationship,
            "contact": self.contact,
            "creditLimit": self.credit_limit,
            "relatedParty": self.related_party,
            "taxExemption": self.tax_exemption,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('account', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('account', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='account',
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
