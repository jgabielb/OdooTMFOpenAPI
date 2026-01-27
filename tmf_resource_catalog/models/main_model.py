from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.resource.catalog'
    _description = 'ResourceCatalog'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char()
    lifecycle_status = fields.Char()
    last_update = fields.Datetime()

    category_json = fields.Json()
    related_party_json = fields.Json()
    valid_for_json = fields.Json()
    raw_json = fields.Json(string="tmfPayload")

    def _get_tmf_api_path(self):
        return "/tmf-api/resourceCatalogManagement/v5/resourceSpecification"

    def to_tmf_json(self, fields=None):
        self.ensure_one()
        data = {
            "id": self.tmf_id or str(self.id),
            "href": f"/tmf-api/resourceCatalogManagement/v5/resourceSpecification/{self.tmf_id or self.id}",
            "@type": "ResourceSpecification",
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "lifecycleStatus": self.lifecycle_status,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
        }
        # include any extra TMF fields provided
        if self.raw_json:
            data.update(self.raw_json)

        if fields:
            allowed = set(fields.split(","))
            data = {k: v for k, v in data.items() if k in allowed or k in ("id", "href")}
        return data
    
    @api.model
    def create_from_tmf(self, payload):
        vals = {
            "name": payload.get("name") or "Unnamed",
            "description": payload.get("description"),
            "version": payload.get("version"),
            "lifecycle_status": payload.get("lifecycleStatus"),
            "last_update": fields.Datetime.now(),
            "raw_json": payload,
        }
        return self.create(vals)
    
    def apply_tmf_patch(self, patch_dict):
        # minimal merge behavior
        self.ensure_one()
        raw = dict(self.raw_json or {})
        raw.update(patch_dict or {})
        vals = {
            "raw_json": raw,
            "name": raw.get("name", self.name),
            "description": raw.get("description", self.description),
            "version": raw.get("version", self.version),
            "lifecycle_status": raw.get("lifecycleStatus", self.lifecycle_status),
            "last_update": fields.Datetime.now(),
        }
        self.write(vals)

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

class TMFResourceSpecification(models.Model):
    _name = "tmf.resource.specification"
    _description = "ResourceSpecification"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char()
    lifecycle_status = fields.Char()
    last_update = fields.Datetime()
    raw_json = fields.Json(string="tmfPayload")

    def to_tmf_json(self, fields=None):
        self.ensure_one()

        # Build base response
        data = {
            "id": self.tmf_id or str(self.id),
            "href": f"/tmf-api/resourceCatalogManagement/v5/resourceSpecification/{self.tmf_id or self.id}",
        }

        # Merge in provided TMF payload first (so @type from CTK is preserved)
        if self.raw_json:
            data.update(self.raw_json)

        # Ensure required fields exist
        data.setdefault("@type", "ResourceSpecification")

        # Only include these if they are real strings (avoid null schema failures)
        if self.lifecycle_status:
            data["lifecycleStatus"] = self.lifecycle_status
        if self.last_update:
            data["lastUpdate"] = self.last_update.isoformat()

        # If fields=... is used, CTK still expects @type, plus id/href
        if fields:
            allowed = set(fields.split(","))
            always = {"id", "href", "@type"}
            data = {k: v for k, v in data.items() if k in allowed or k in always}

        return data

    @api.model
    def create_from_tmf(self, payload):
        return self.create({
            "name": payload.get("name") or "Unnamed",
            "description": payload.get("description"),
            "version": payload.get("version"),
            "lifecycle_status": payload.get("lifecycleStatus"),
            "last_update": fields.Datetime.now(),
            "raw_json": payload,
        })

    def apply_tmf_patch(self, patch_dict):
        self.ensure_one()
        raw = dict(self.raw_json or {})
        raw.update(patch_dict or {})
        self.write({
            "raw_json": raw,
            "name": raw.get("name", self.name),
            "description": raw.get("description", self.description),
            "version": raw.get("version", self.version),
            "lifecycle_status": raw.get("lifecycleStatus", self.lifecycle_status),
            "last_update": fields.Datetime.now(),
        })