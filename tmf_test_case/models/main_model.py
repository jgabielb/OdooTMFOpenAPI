import json
from odoo import api, fields, models


API_BASE = "/tmf-api/testCase/v4"


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


class _TMF704ArtifactMixin(models.AbstractModel):
    _name = "tmf.test.artifact.mixin"
    _description = "TMF704 Common Artifact Mixin"
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


class TMFTestCase(models.Model):
    _name = "tmf.test.case"
    _description = "TMF704 TestCase"
    _inherit = ["tmf.test.artifact.mixin"]

    test_case_definition_json = fields.Text(string="testCaseDefinition")

    def _get_tmf_api_path(self):
        return "/testCase/v4/testCase"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestCase"
        payload["testCaseDefinition"] = _loads(self.test_case_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "testCaseDefinition" in data:
            vals["test_case_definition_json"] = _dumps(data.get("testCaseDefinition"))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="testCase",
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
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testCase",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestSuite(models.Model):
    _name = "tmf.test.suite"
    _description = "TMF704 TestSuite"
    _inherit = ["tmf.test.artifact.mixin"]

    test_suite_definition_json = fields.Text(string="testSuiteDefinition")

    def _get_tmf_api_path(self):
        return "/testCase/v4/testSuite"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestSuite"
        payload["testSuiteDefinition"] = _loads(self.test_suite_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "testSuiteDefinition" in data:
            vals["test_suite_definition_json"] = _dumps(data.get("testSuiteDefinition"))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="testSuite",
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
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testSuite",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFNonFunctionalTestModel(models.Model):
    _name = "tmf.non.functional.test.model"
    _description = "TMF704 NonFunctionalTestModel"
    _inherit = ["tmf.test.artifact.mixin"]

    non_functional_test_model_definition_json = fields.Text(string="nonFunctionalTestModelDefinition")

    def _get_tmf_api_path(self):
        return "/testCase/v4/nonFunctionalTestModel"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "NonFunctionalTestModel"
        payload["nonFunctionalTestModelDefinition"] = _loads(self.non_functional_test_model_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "nonFunctionalTestModelDefinition" in data:
            vals["non_functional_test_model_definition_json"] = _dumps(data.get("nonFunctionalTestModelDefinition"))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="nonFunctionalTestModel",
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
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="nonFunctionalTestModel",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
