from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.geographic.site'
    _description = 'GeographicSite'
    _inherit = ['tmf.model.mixin']

    code = fields.Char(string="code", help="A code that may be used for some addressing schemes eg: [ANSI T1.253-1999]")
    description = fields.Char(string="description", help="Text describing additional information regarding the site")
    name = fields.Char(string="name", help="A user-friendly name for the place, such as [Paris Store], [London Store], [Main Home]")
    status = fields.Char(string="status", help="The condition of the GeographicSite, such as planned, underConstruction, cancelled, active, inactive")
    calendar = fields.Char(string="calendar", help="")
    place = fields.Char(string="place", help="")
    related_party = fields.Char(string="relatedParty", help="")
    site_relationship = fields.Char(string="siteRelationship", help="")

    def _get_tmf_api_path(self):
        return "/geographic_siteManagement/v4/GeographicSite"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "GeographicSite",
            "code": self.code,
            "description": self.description,
            "name": self.name,
            "status": self.status,
            "calendar": self.calendar,
            "place": self.place,
            "relatedParty": self.related_party,
            "siteRelationship": self.site_relationship,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('geographicSite', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('geographicSite', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='geographicSite',
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
