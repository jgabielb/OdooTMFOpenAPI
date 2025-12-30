from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.geographic.location'
    _description = 'GeographicLocation'
    _inherit = ['tmf.model.mixin']

    bbox = fields.Char(string="bbox", help="A bounding box array that contains the geometry. The axes order follows the axes order of the geomet")

    def _get_tmf_api_path(self):
        return "/geographic_locationManagement/v4/GeographicLocation"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "GeographicLocation",
            "bbox": self.bbox,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('geographicLocation', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('geographicLocation', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='geographicLocation',
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
