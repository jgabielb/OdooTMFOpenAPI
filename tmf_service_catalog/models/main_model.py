from odoo import models, fields, api
from odoo.tools import date_utils

class TMFServiceCatalog(models.Model):
    _name = 'tmf.service.catalog'
    _description = 'TMF633 ServiceCatalog'
    _inherit = ['tmf.model.mixin']

    # TMF core fields
    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    version = fields.Char(string="version")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    last_update = fields.Datetime(string="lastUpdate")

    # TMF633 shapes (these are NOT strings in TMF — they are arrays/objects)
    # Minimal: store JSON until you model them properly with relational tables.
    category = fields.Json(string="category")          # array of ServiceCategoryRef
    related_party = fields.Json(string="relatedParty") # array of RelatedPartyRefOrPartyRoleRef
    valid_for = fields.Json(string="validFor")         # TimePeriod object

    def _get_tmf_api_path(self):
        # TMF633 v4 resource base
        return "/tmf-api/serviceCatalogManagement/v4/"

    def _tmf_href(self):
        self.ensure_one()
        # if tmf_id exists use it, else fallback to Odoo id
        rid = self.tmf_id or str(self.id)
        return f"{self._get_tmf_api_path()}/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id or str(self.id),
            "href": self._tmf_href(),
            "@type": "ServiceCatalog",
            "name": self.name or "",
            "description": self.description,
            "version": self.version,
            "lifecycleStatus": self.lifecycle_status or "active",
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "category": self.category or [],
            "relatedParty": self.related_party or [],
            "validFor": self.valid_for or None,
        }

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("last_update", now)
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify('serviceCatalog', 'create', rec)
        return recs

    def write(self, vals):
        vals.setdefault("last_update", fields.Datetime.now())
        res = super().write(vals)
        for rec in self:
            rec._notify('serviceCatalog', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceCatalog',
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

class TMFServiceSpecification(models.Model):
    _name = 'tmf.service.specification'
    _description = 'TMF633 ServiceSpecification'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char()
    lifecycle_status = fields.Char(string="lifecycleStatus", default="active")
    last_update = fields.Datetime(string="lastUpdate")

    is_bundle = fields.Boolean(string="isBundle", default=False)

    # keep JSON blobs for now (optional but TMF commonly carries them)
    related_party = fields.Json(string="relatedParty")
    valid_for = fields.Json(string="validFor")

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"

    def _tmf_href(self):
        self.ensure_one()
        rid = self.tmf_id or str(self.id)
        return f"{self._get_tmf_api_path()}/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id or str(self.id),
            "href": self._tmf_href(),
            "@type": "ServiceSpecification",
            "name": self.name or "",
            "description": self.description,
            "version": self.version,
            "lifecycleStatus": self.lifecycle_status or "active",
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "isBundle": bool(self.is_bundle),
            "relatedParty": self.related_party or [],
            "validFor": self.valid_for or None,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ls = vals.get("lifecycle_status")
            if ls in (False, None, ""):
                vals["lifecycle_status"] = "active"
            else:
                vals["lifecycle_status"] = str(ls).strip().lower()
        return super().create(vals_list)

    def write(self, vals):
        vals.setdefault("last_update", fields.Datetime.now())
        res = super().write(vals)
        for rec in self:
            rec._notify('serviceSpecification', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceSpecification',
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