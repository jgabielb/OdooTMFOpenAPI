from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.usage.consumption'
    _description = 'UsageConsumption'
    _inherit = ['tmf.model.mixin']

    creation_date = fields.Datetime(string="creationDate", help="Date and time of the request creation")
    description = fields.Char(string="description", help="Free short text describing the usage consumption content")
    last_update = fields.Datetime(string="lastUpdate", help="Date when the status was last changed")
    name = fields.Char(string="name", help="Usage consumption name")
    bucket_ref_or_value = fields.Char(string="bucketRefOrValue", help="Bucket(s) included in the offer or option subscribed.")
    logical_resource = fields.Char(string="logicalResource", help="")
    party_account = fields.Char(string="partyAccount", help="A reference to the account that owns the bucket")
    product = fields.Char(string="product", help="")
    related_party = fields.Char(string="relatedParty", help="Reference and role of the related parties for which the usage consumption is requested")
    service = fields.Char(string="service", help="")
    state = fields.Char(string="state", help="State of the report report defined in the state engine")
    valid_period = fields.Char(string="validPeriod", help="Validity period")

    def _get_tmf_api_path(self):
        return "/usage_consumptionManagement/v4/UsageConsumption"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "UsageConsumption",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "name": self.name,
            "bucketRefOrValue": self.bucket_ref_or_value,
            "logicalResource": self.logical_resource,
            "partyAccount": self.party_account,
            "product": self.product,
            "relatedParty": self.related_party,
            "service": self.service,
            "state": self.state,
            "validPeriod": self.valid_period,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('usageConsumption', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('usageConsumption', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='usageConsumption',
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
