import json
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


class _TMF706ArtifactMixin(models.AbstractModel):
    _name = "tmf.test.data.artifact.mixin"
    _description = "TMF706 Common Artifact Mixin"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    version = fields.Char(string="version")
    version_description = fields.Char(string="versionDescription")
    agreement_json = fields.Text(string="agreement")
    attribute_json = fields.Text(string="attribute")
    related_party_json = fields.Text(string="relatedParty")
    state = fields.Char(string="state")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _artifact_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "version": self.version,
            "versionDescription": self.version_description,
            "agreement": _loads(self.agreement_json),
            "attribute": _loads(self.attribute_json),
            "relatedParty": _loads(self.related_party_json),
            "state": self.state,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _artifact_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("version", "version"),
            ("versionDescription", "version_description"),
            ("state", "state"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if "agreement" in data:
            vals["agreement_json"] = _dumps(data.get("agreement"))
        if "attribute" in data:
            vals["attribute_json"] = _dumps(data.get("attribute"))
        if "relatedParty" in data:
            vals["related_party_json"] = _dumps(data.get("relatedParty"))
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


class TMFTestDataInstance(models.Model):
    _name = "tmf.test.data.instance"
    _description = "TMF706 TestDataInstance"
    _inherit = ["tmf.test.data.artifact.mixin"]

    test_data_instance_definition_json = fields.Text(string="testDataInstanceDefinition")

    def _get_tmf_api_path(self):
        return "/testData/v4/testDataInstance"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestDataInstance"
        payload["testDataInstanceDefinition"] = _loads(self.test_data_instance_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "testDataInstanceDefinition" in data:
            vals["test_data_instance_definition_json"] = _dumps(data.get("testDataInstanceDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testDataInstance", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testDataInstance", "update", rec)
            if state_changed:
                self._notify("testDataInstance", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testDataInstance",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestDataSchema(models.Model):
    _name = "tmf.test.data.schema"
    _description = "TMF706 TestDataSchema"
    _inherit = ["tmf.test.data.artifact.mixin"]

    test_data_schema_definition_json = fields.Text(string="testDataSchemaDefinition")

    def _get_tmf_api_path(self):
        return "/testData/v4/testDataSchema"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestDataSchema"
        payload["testDataSchemaDefinition"] = _loads(self.test_data_schema_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "testDataSchemaDefinition" in data:
            vals["test_data_schema_definition_json"] = _dumps(data.get("testDataSchemaDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testDataSchema", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testDataSchema", "update", rec)
            if state_changed:
                self._notify("testDataSchema", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testDataSchema",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
