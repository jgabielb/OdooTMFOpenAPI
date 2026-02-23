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


class _TMF707ResultMixin(models.AbstractModel):
    _name = "tmf.test.result.mixin"
    _description = "TMF707 Common Result Mixin"
    _inherit = ["tmf.model.mixin"]

    test_execution_json = fields.Text(string="testExecution")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _result_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "testExecution": _loads(self.test_execution_json),
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _result_from_tmf_json(self, data):
        vals = {}
        if "testExecution" in data:
            vals["test_execution_json"] = _dumps(data.get("testExecution"))
        if "@type" in data:
            vals["tmf_type_value"] = data.get("@type")
        if "@baseType" in data:
            vals["base_type"] = data.get("@baseType")
        if "@schemaLocation" in data:
            vals["schema_location"] = data.get("@schemaLocation")
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


class TMFTestCaseResult(models.Model):
    _name = "tmf.test.case.result"
    _description = "TMF707 TestCaseResult"
    _inherit = ["tmf.test.result.mixin"]

    test_case_result_definition_json = fields.Text(string="testCaseResultDefinition")

    def _get_tmf_api_path(self):
        return "/testResult/v4/testCaseResult"

    def to_tmf_json(self):
        payload = self._result_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestCaseResult"
        payload["testCaseResultDefinition"] = _loads(self.test_case_result_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._result_from_tmf_json(data)
        if "testCaseResultDefinition" in data:
            vals["test_case_result_definition_json"] = _dumps(data.get("testCaseResultDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testCaseResult", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("testCaseResult", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testCaseResult",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestSuiteResult(models.Model):
    _name = "tmf.test.suite.result"
    _description = "TMF707 TestSuiteResult"
    _inherit = ["tmf.test.result.mixin"]

    test_suite_result_definition_json = fields.Text(string="testSuiteResultDefinition")

    def _get_tmf_api_path(self):
        return "/testResult/v4/testSuiteResult"

    def to_tmf_json(self):
        payload = self._result_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestSuiteResult"
        payload["testSuiteResultDefinition"] = _loads(self.test_suite_result_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._result_from_tmf_json(data)
        if "testSuiteResultDefinition" in data:
            vals["test_suite_result_definition_json"] = _dumps(data.get("testSuiteResultDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testSuiteResult", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("testSuiteResult", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testSuiteResult",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFNonFunctionalTestResult(models.Model):
    _name = "tmf.non.functional.test.result"
    _description = "TMF707 NonFunctionalTestResult"
    _inherit = ["tmf.test.result.mixin"]

    non_functional_test_result_definition_json = fields.Text(string="nonFunctionalTestResultDefinition")

    def _get_tmf_api_path(self):
        return "/testResult/v4/nonFunctionalTestResult"

    def to_tmf_json(self):
        payload = self._result_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "NonFunctionalTestResult"
        payload["nonFunctionalTestResultDefinition"] = _loads(self.non_functional_test_result_definition_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._result_from_tmf_json(data)
        if "nonFunctionalTestResultDefinition" in data:
            vals["non_functional_test_result_definition_json"] = _dumps(data.get("nonFunctionalTestResultDefinition"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("nonFunctionalTestResult", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("nonFunctionalTestResult", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="nonFunctionalTestResult",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
