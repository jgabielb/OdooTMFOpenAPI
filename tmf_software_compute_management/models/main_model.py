import json
from datetime import datetime, timezone
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None}


class _TMF730CommonMixin(models.AbstractModel):
    _name = "tmf.software.compute.common.mixin"
    _description = "TMF730 Common Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    category = fields.Char(string="category")
    description = fields.Char(string="description")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location or "https://tmforum.org/schema",
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("name", "name"),
            ("category", "category"),
            ("description", "description"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _notify(self, api_name, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass


class TMFSoftwareComputeResource(models.Model):
    _name = "tmf.software.compute.resource"
    _description = "TMF730 Resource"
    _inherit = ["tmf.software.compute.common.mixin"]

    resource_version = fields.Char(string="resourceVersion")
    start_operating_date = fields.Char(string="startOperatingDate")
    end_operating_date = fields.Char(string="endOperatingDate")
    administrative_state = fields.Char(string="administrativeState")
    operational_state = fields.Char(string="operationalState")
    resource_status = fields.Char(string="resourceStatus")
    usage_state = fields.Char(string="usageState")

    activation_feature_json = fields.Text(string="activationFeature")
    attachment_json = fields.Text(string="attachment")
    note_json = fields.Text(string="note")
    place_json = fields.Text(string="place")
    related_party_json = fields.Text(string="relatedParty")
    resource_characteristic_json = fields.Text(string="resourceCharacteristic")
    resource_relationship_json = fields.Text(string="resourceRelationship")
    resource_specification_json = fields.Text(string="resourceSpecification")

    def _get_tmf_api_path(self):
        return "/softwareCompute/v4/resource"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "resourceVersion": self.resource_version,
                "startOperatingDate": self.start_operating_date,
                "endOperatingDate": self.end_operating_date,
                "administrativeState": self.administrative_state,
                "operationalState": self.operational_state,
                "resourceStatus": self.resource_status,
                "usageState": self.usage_state,
                "activationFeature": _loads(self.activation_feature_json),
                "attachment": _loads(self.attachment_json),
                "note": _loads(self.note_json),
                "place": _loads(self.place_json),
                "relatedParty": _loads(self.related_party_json),
                "resourceCharacteristic": _loads(self.resource_characteristic_json),
                "resourceRelationship": _loads(self.resource_relationship_json),
                "resourceSpecification": _loads(self.resource_specification_json),
                "@type": self.tmf_type_value or "ResourceFunction",
                "@baseType": self.base_type or "Resource",
            }
        )
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("resourceVersion", "resource_version"),
            ("startOperatingDate", "start_operating_date"),
            ("endOperatingDate", "end_operating_date"),
            ("administrativeState", "administrative_state"),
            ("operationalState", "operational_state"),
            ("resourceStatus", "resource_status"),
            ("usageState", "usage_state"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("activationFeature", "activation_feature_json"),
            ("attachment", "attachment_json"),
            ("note", "note_json"),
            ("place", "place_json"),
            ("relatedParty", "related_party_json"),
            ("resourceCharacteristic", "resource_characteristic_json"),
            ("resourceRelationship", "resource_relationship_json"),
            ("resourceSpecification", "resource_specification_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("softwareComputeResource", "create", rec)
        return recs

    def write(self, vals):
        state_changed = any(k in vals for k in ("administrative_state", "operational_state", "resource_status", "usage_state"))
        res = super().write(vals)
        for rec in self:
            self._notify("softwareComputeResource", "update", rec)
            if state_changed:
                self._notify("softwareComputeResource", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="softwareComputeResource",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFSoftwareComputeResourceSpecification(models.Model):
    _name = "tmf.software.compute.resource.specification"
    _description = "TMF730 ResourceSpecification"
    _inherit = ["tmf.software.compute.common.mixin"]

    is_bundle = fields.Boolean(string="isBundle")
    last_update = fields.Char(string="lastUpdate")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    version = fields.Char(string="version")

    attachment_json = fields.Text(string="attachment")
    feature_specification_json = fields.Text(string="featureSpecification")
    related_party_json = fields.Text(string="relatedParty")
    resource_spec_characteristic_json = fields.Text(string="resourceSpecCharacteristic")
    resource_spec_relationship_json = fields.Text(string="resourceSpecRelationship")
    target_resource_schema_json = fields.Text(string="targetResourceSchema")
    valid_for_json = fields.Text(string="validFor")

    def _get_tmf_api_path(self):
        return "/softwareCompute/v4/resourceSpecification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "isBundle": self.is_bundle,
                "lastUpdate": self.last_update,
                "lifecycleStatus": self.lifecycle_status,
                "version": self.version,
                "attachment": _loads(self.attachment_json),
                "featureSpecification": _loads(self.feature_specification_json),
                "relatedParty": _loads(self.related_party_json),
                "resourceSpecCharacteristic": _loads(self.resource_spec_characteristic_json),
                "resourceSpecRelationship": _loads(self.resource_spec_relationship_json),
                "targetResourceSchema": _loads(self.target_resource_schema_json),
                "validFor": _loads(self.valid_for_json),
                "@type": self.tmf_type_value or "ResourceFunctionSpecification",
                "@baseType": self.base_type or "ResourceSpecification",
            }
        )
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("isBundle", "is_bundle"),
            ("lastUpdate", "last_update"),
            ("lifecycleStatus", "lifecycle_status"),
            ("version", "version"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("attachment", "attachment_json"),
            ("featureSpecification", "feature_specification_json"),
            ("relatedParty", "related_party_json"),
            ("resourceSpecCharacteristic", "resource_spec_characteristic_json"),
            ("resourceSpecRelationship", "resource_spec_relationship_json"),
            ("targetResourceSchema", "target_resource_schema_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_update", vals.get("last_update") or self._now_iso())
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("softwareComputeResourceSpecification", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("softwareComputeResourceSpecification", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="softwareComputeResourceSpecification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
