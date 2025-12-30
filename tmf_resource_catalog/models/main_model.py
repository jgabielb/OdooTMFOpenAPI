from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.resource.catalog'
    _description = 'ResourceCatalog'
    _inherit = ['tmf.model.mixin']

    description = fields.Char(string="description", help="Description of this catalog")
    last_update = fields.Datetime(string="lastUpdate", help="Date and time of the last update")
    lifecycle_status = fields.Char(string="lifecycleStatus", help="Used to indicate the current lifecycle status")
    name = fields.Char(string="name", help="Name of the catalog")
    version = fields.Char(string="version", help="Catalog version")
    category = fields.Char(string="category", help="List of root categories contained in this catalog")
    related_party = fields.Char(string="relatedParty", help="List of parties involved in this catalog")
    valid_for = fields.Char(string="validFor", help="The period for which the catalog is valid")

    def _get_tmf_api_path(self):
        return "/resource_catalogManagement/v4/ResourceCatalog"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ResourceCatalog",
            "description": self.description,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status,
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "relatedParty": self.related_party,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('resourceCatalog', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('resourceCatalog', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='resourceCatalog',
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
