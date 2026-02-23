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


class _TMF705ArtifactMixin(models.AbstractModel):
    _name = "tmf.test.environment.artifact.mixin"
    _description = "TMF705 Common Artifact Mixin"
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


class TMFAbstractEnvironment(models.Model):
    _name = "tmf.abstract.environment"
    _description = "TMF705 AbstractEnvironment"
    _inherit = ["tmf.test.environment.artifact.mixin"]

    abstract_environment_definition_json = fields.Text(string="abstractEnvironmentDefinition")

    def _get_tmf_api_path(self):
        return "/testEnvironment/v4/abstractEnvironment"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "AbstractEnvironment"
        payload["abstractEnvironmentDefinition"] = _loads(self.abstract_environment_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "abstractEnvironmentDefinition" in data:
            vals["abstract_environment_definition_json"] = _dumps(data.get("abstractEnvironmentDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("abstractEnvironment", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("abstractEnvironment", "update", rec)
            if state_changed:
                self._notify("abstractEnvironment", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="abstractEnvironment",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFConcreteEnvironmentMetaModel(models.Model):
    _name = "tmf.concrete.environment.meta.model"
    _description = "TMF705 ConcreteEnvironmentMetaModel"
    _inherit = ["tmf.test.environment.artifact.mixin"]

    concrete_environment_meta_model_definition_json = fields.Text(string="concreteEnvironmentMetaModelDefinition")

    def _get_tmf_api_path(self):
        return "/testEnvironment/v4/concreteEnvironmentMetaModel"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "ConcreteEnvironmentMetaModel"
        payload["concreteEnvironmentMetaModelDefinition"] = _loads(self.concrete_environment_meta_model_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "concreteEnvironmentMetaModelDefinition" in data:
            vals["concrete_environment_meta_model_definition_json"] = _dumps(data.get("concreteEnvironmentMetaModelDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("concreteEnvironmentMetaModel", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("concreteEnvironmentMetaModel", "update", rec)
            if state_changed:
                self._notify("concreteEnvironmentMetaModel", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="concreteEnvironmentMetaModel",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestResourceAPI(models.Model):
    _name = "tmf.test.resource.api"
    _description = "TMF705 TestResourceAPI"
    _inherit = ["tmf.test.environment.artifact.mixin"]

    test_resource_api_definition_json = fields.Text(string="testResourceAPIDefinition")

    def _get_tmf_api_path(self):
        return "/testEnvironment/v4/testResourceAPI"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestResourceAPI"
        payload["testResourceAPIDefinition"] = _loads(self.test_resource_api_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "testResourceAPIDefinition" in data:
            vals["test_resource_api_definition_json"] = _dumps(data.get("testResourceAPIDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testResourceAPI", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testResourceAPI", "update", rec)
            if state_changed:
                self._notify("testResourceAPI", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testResourceAPI",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFProvisioningArtifact(models.Model):
    _name = "tmf.provisioning.artifact"
    _description = "TMF705 ProvisioningArtifact"
    _inherit = ["tmf.test.environment.artifact.mixin"]

    provisioning_artifact_definition_json = fields.Text(string="provisioningArtifactDefinition")

    def _get_tmf_api_path(self):
        return "/testEnvironment/v4/provisioningArtifact"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "ProvisioningArtifact"
        payload["provisioningArtifactDefinition"] = _loads(self.provisioning_artifact_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "provisioningArtifactDefinition" in data:
            vals["provisioning_artifact_definition_json"] = _dumps(data.get("provisioningArtifactDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("provisioningArtifact", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("provisioningArtifact", "update", rec)
            if state_changed:
                self._notify("provisioningArtifact", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="provisioningArtifact",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
