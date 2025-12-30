from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.usage'
    _description = 'Usage'
    _inherit = ['tmf.model.mixin']

    description = fields.Char(string="description", help="Description of usage")
    usage_date = fields.Datetime(string="usageDate", help="Date of usage")
    usage_type = fields.Char(string="usageType", help="Type of usage")
    rated_product_usage = fields.Char(string="ratedProductUsage", help="")
    related_party = fields.Char(string="relatedParty", help="")
    status = fields.Char(string="status", help="")
    usage_characteristic = fields.Char(string="usageCharacteristic", help="")
    usage_specification = fields.Char(string="usageSpecification", help="")

    def _get_tmf_api_path(self):
        return "/usageManagement/v4/Usage"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Usage",
            "description": self.description,
            "usageDate": self.usage_date.isoformat() if self.usage_date else None,
            "usageType": self.usage_type,
            "ratedProductUsage": self.rated_product_usage,
            "relatedParty": self.related_party,
            "status": self.status,
            "usageCharacteristic": self.usage_characteristic,
            "usageSpecification": self.usage_specification,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('usage', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('usage', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='usage',
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
