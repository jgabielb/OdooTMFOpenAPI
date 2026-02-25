# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import uuid


def _safe_json_load(v, default):
    if v in (None, "", False):
        return default
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return default


def _safe_json_dump(v):
    if v in (None, "", False):
        return False
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    # already a string -> keep it
    return v

class TMFEntitySpecification(models.Model):
    _name = "tmf.entity.specification"
    _description = "TMF662 EntitySpecification"
    _inherit = ["tmf.model.mixin"]

    # Minimal top-level fields CTK filters on
    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char()
    lifecycle_status = fields.Char(string="lifecycleStatus")
    last_update = fields.Datetime(string="lastUpdate")
    is_bundle = fields.Boolean(string="isBundle", default=False)

    # Store complex TMF structures as JSON text
    valid_for_json = fields.Text(string="validFor")
    attachment_json = fields.Text(string="attachment")
    related_party_json = fields.Text(string="relatedParty")
    constraint_json = fields.Text(string="constraint")
    spec_characteristic_json = fields.Text(string="specCharacteristic")
    target_entity_schema_json = fields.Text(string="targetEntitySchema")
    entity_spec_relationship_json = fields.Text(string="entitySpecRelationship")

    def _get_tmf_api_path(self):
        return "/entityCatalogManagement/v4/entitySpecification"


    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "validFor": _safe_json_load(self.valid_for_json, None),
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status,
            "isBundle": bool(self.is_bundle),

            "attachment": _safe_json_load(self.attachment_json, []),
            "relatedParty": _safe_json_load(self.related_party_json, []),
            "constraint": _safe_json_load(self.constraint_json, []),
            "specCharacteristic": _safe_json_load(self.spec_characteristic_json, []),
            "targetEntitySchema": _safe_json_load(self.target_entity_schema_json, None),
            "entitySpecRelationship": _safe_json_load(self.entity_spec_relationship_json, []),

            "@type": "EntitySpecification",
        }
        return self._tmf_normalize_payload(payload)

    def tmf_from_json(self, data: dict, for_patch: bool):
        vals = {}

        def put(field_name, value):
            if for_patch and value is None:
                return
            vals[field_name] = value

        if "name" in data:
            put("name", data.get("name"))
        if "description" in data:
            put("description", data.get("description"))
        if "version" in data:
            put("version", data.get("version"))
        if "lifecycleStatus" in data:
            put("lifecycle_status", data.get("lifecycleStatus"))
        if "isBundle" in data:
            put("is_bundle", bool(data.get("isBundle")))

        if "validFor" in data:
            put("valid_for_json", _safe_json_dump(data.get("validFor")))
        if "attachment" in data:
            put("attachment_json", _safe_json_dump(data.get("attachment") or []))
        if "relatedParty" in data:
            put("related_party_json", _safe_json_dump(data.get("relatedParty") or []))
        if "constraint" in data:
            put("constraint_json", _safe_json_dump(data.get("constraint") or []))
        if "specCharacteristic" in data:
            put("spec_characteristic_json", _safe_json_dump(data.get("specCharacteristic") or []))
        if "targetEntitySchema" in data:
            put("target_entity_schema_json", _safe_json_dump(data.get("targetEntitySchema")))
        if "entitySpecRelationship" in data:
            put("entity_spec_relationship_json", _safe_json_dump(data.get("entitySpecRelationship") or []))

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("tmf_id", str(uuid.uuid4()))
        return super().create(vals_list)

class TMFEntityCatalog(models.Model):
    _name = "tmf.entity.catalog"
    _description = "TMF662 EntityCatalog"
    _inherit = ["tmf.model.mixin"]

    # TMF662 fields
    name = fields.Char(required=True)  # POST mandatory :contentReference[oaicite:9]{index=9}
    description = fields.Char()
    version = fields.Char()
    lifecycle_status = fields.Char(string="lifecycleStatus")
    last_update = fields.Datetime(string="lastUpdate")

    # Structured TMF fields stored as JSON text (portable across Odoo versions)
    # TMF662: category is array of EntityCategoryRef objects :contentReference[oaicite:10]{index=10}
    category_json = fields.Text(string="category")          # JSON list
    related_party_json = fields.Text(string="relatedParty") # JSON list
    valid_for_json = fields.Text(string="validFor")         # JSON dict

    def _get_tmf_api_path(self):
        # TMF662 path uses /entityCatalog (lower camel) :contentReference[oaicite:11]{index=11}
        return "/entityCatalogManagement/v4/entityCatalog"

    # --------
    # TMF serialization
    # --------
    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "validFor": _safe_json_load(self.valid_for_json, None),
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status,
            "relatedParty": _safe_json_load(self.related_party_json, []),
            "category": _safe_json_load(self.category_json, []),

            # Polymorphism meta-attributes (include if your mixin sets them; otherwise keep defaults)
            "@type": "EntityCatalog",  # :contentReference[oaicite:12]{index=12}
            # Optional: "@schemaLocation", "@baseType"
        }
        return self._tmf_normalize_payload(payload)

    # --------
    # TMF -> Odoo mapping helper
    # --------
    def tmf_from_json(self, data: dict, for_patch: bool):
        """
        Map TMF JSON payload into Odoo vals.

        for_patch=True:
          - absent fields are ignored
          - only included fields are updated
        """
        vals = {}

        def put(field_name, value):
            if for_patch and value is None:
                return
            vals[field_name] = value

        # Simple
        if "name" in data:
            put("name", data.get("name"))
        if "description" in data:
            put("description", data.get("description"))
        if "version" in data:
            put("version", data.get("version"))
        if "lifecycleStatus" in data:
            put("lifecycle_status", data.get("lifecycleStatus"))

        # Structured
        if "category" in data:
            put("category_json", _safe_json_dump(data.get("category") or []))
        if "relatedParty" in data:
            put("related_party_json", _safe_json_dump(data.get("relatedParty") or []))
        if "validFor" in data:
            put("valid_for_json", _safe_json_dump(data.get("validFor")))

        return vals

    # --------
    # ID generation (if your mixin doesn't do it)
    # --------
    @api.model_create_multi
    def create(self, vals_list):
        # Ensure tmf_id exists (many of your modules follow this pattern)
        for vals in vals_list:
            vals.setdefault("tmf_id", str(uuid.uuid4()))
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify("entityCatalog", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._notify("entityCatalog", "update", rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="entityCatalog",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
