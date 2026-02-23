import json
from odoo import api, fields, models


API_BASE = "/tmf-api/entityInventory/v4"


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


class TMFEntity(models.Model):
    _name = "tmf.entity"
    _description = "TMF703 Entity"
    _inherit = ["tmf.model.mixin"]

    tmf_type_value = fields.Char(string="@type", default="Entity")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/entityInventory/v4/entity"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type_value or "Entity",
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def from_tmf_json(self, data, partial=False):
        vals = {}
        if "@type" in data:
            vals["tmf_type_value"] = data.get("@type")
        if "@baseType" in data:
            vals["base_type"] = data.get("@baseType")
        if "@schemaLocation" in data:
            vals["schema_location"] = data.get("@schemaLocation")
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="entity",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="entity",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFAssociation(models.Model):
    _name = "tmf.entity.association"
    _description = "TMF703 Association"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(required=True)
    association_role = fields.Char(string="associationRole", required=True)
    description = fields.Char()
    lifecycle_status = fields.Char(string="lifecycleStatus")
    version = fields.Char()
    last_update = fields.Datetime(string="lastUpdate")
    association_spec_json = fields.Text(string="associationSpec")
    constraint_json = fields.Text(string="constraint")
    valid_for_json = fields.Text(string="validFor")
    tmf_type_value = fields.Char(string="@type", default="Association")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/entityInventory/v4/association"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "associationRole": self.association_role,
            "description": self.description,
            "lifecycleStatus": self.lifecycle_status,
            "version": self.version,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "associationSpec": _loads(self.association_spec_json),
            "constraint": _loads(self.constraint_json),
            "validFor": _loads(self.valid_for_json),
            "@type": self.tmf_type_value or "Association",
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("name", "name"),
            ("associationRole", "association_role"),
            ("description", "description"),
            ("lifecycleStatus", "lifecycle_status"),
            ("version", "version"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if "lastUpdate" in data:
            vals["last_update"] = data.get("lastUpdate")
        if "associationSpec" in data:
            vals["association_spec_json"] = _dumps(data.get("associationSpec"))
        if "constraint" in data:
            vals["constraint_json"] = _dumps(data.get("constraint"))
        if "validFor" in data:
            vals["valid_for_json"] = _dumps(data.get("validFor"))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="association",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="association",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
