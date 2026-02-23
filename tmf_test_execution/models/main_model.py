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


class _TMF708ExecutionMixin(models.AbstractModel):
    _name = "tmf.test.execution.mixin"
    _description = "TMF708 Common Execution Mixin"
    _inherit = ["tmf.model.mixin"]

    data_correlation_id = fields.Char(string="dataCorrelationId")
    state = fields.Char(string="state")
    test_environment_provisioning_execution_json = fields.Text(string="testEnvironmentProvisioningExecution")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _execution_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "dataCorrelationId": self.data_correlation_id,
            "state": self.state,
            "testEnvironmentProvisioningExecution": _loads(self.test_environment_provisioning_execution_json),
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _execution_from_tmf_json(self, data):
        vals = {}
        if "dataCorrelationId" in data:
            vals["data_correlation_id"] = data.get("dataCorrelationId")
        if "state" in data:
            vals["state"] = data.get("state")
        if "testEnvironmentProvisioningExecution" in data:
            vals["test_environment_provisioning_execution_json"] = _dumps(data.get("testEnvironmentProvisioningExecution"))
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


class TMFTestEnvironmentAllocationExecution(models.Model):
    _name = "tmf.test.environment.allocation.execution"
    _description = "TMF708 TestEnvironmentAllocationExecution"
    _inherit = ["tmf.test.execution.mixin"]

    abstract_environment_json = fields.Text(string="abstractEnvironment")
    resource_manager_url = fields.Char(string="resourceManagerUrl")

    def _get_tmf_api_path(self):
        return "/testExecution/v4/testEnvironmentAllocationExecution"

    def to_tmf_json(self):
        payload = self._execution_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestEnvironmentAllocationExecution"
        payload["abstractEnvironment"] = _loads(self.abstract_environment_json)
        payload["resourceManagerUrl"] = self.resource_manager_url
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._execution_from_tmf_json(data)
        if "abstractEnvironment" in data:
            vals["abstract_environment_json"] = _dumps(data.get("abstractEnvironment"))
        if "resourceManagerUrl" in data:
            vals["resource_manager_url"] = data.get("resourceManagerUrl")
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testEnvironmentAllocationExecution", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testEnvironmentAllocationExecution", "update", rec)
            if state_changed:
                self._notify("testEnvironmentAllocationExecution", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testEnvironmentAllocationExecution",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestEnvironmentProvisioningExecution(models.Model):
    _name = "tmf.test.environment.provisioning.execution"
    _description = "TMF708 TestEnvironmentProvisioningExecution"
    _inherit = ["tmf.test.execution.mixin"]

    test_environment_allocation_execution_json = fields.Text(string="testEnvironmentAllocationExecution")

    def _get_tmf_api_path(self):
        return "/testExecution/v4/testEnvironmentProvisioningExecution"

    def to_tmf_json(self):
        payload = self._execution_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestEnvironmentProvisioningExecution"
        payload["testEnvironmentAllocationExecution"] = _loads(self.test_environment_allocation_execution_json)
        return payload

    def from_tmf_json(self, data, partial=False):
        vals = self._execution_from_tmf_json(data)
        if "testEnvironmentAllocationExecution" in data:
            vals["test_environment_allocation_execution_json"] = _dumps(data.get("testEnvironmentAllocationExecution"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testEnvironmentProvisioningExecution", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testEnvironmentProvisioningExecution", "update", rec)
            if state_changed:
                self._notify("testEnvironmentProvisioningExecution", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testEnvironmentProvisioningExecution",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestSuiteExecution(models.Model):
    _name = "tmf.test.suite.execution"
    _description = "TMF708 TestSuiteExecution"
    _inherit = ["tmf.test.execution.mixin"]

    def _get_tmf_api_path(self):
        return "/testExecution/v4/testSuiteExecution"

    def to_tmf_json(self):
        payload = self._execution_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestSuiteExecution"
        return payload

    def from_tmf_json(self, data, partial=False):
        return self._execution_from_tmf_json(data)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testSuiteExecution", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testSuiteExecution", "update", rec)
            if state_changed:
                self._notify("testSuiteExecution", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testSuiteExecution",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFTestCaseExecution(models.Model):
    _name = "tmf.test.case.execution"
    _description = "TMF708 TestCaseExecution"
    _inherit = ["tmf.test.execution.mixin"]

    def _get_tmf_api_path(self):
        return "/testExecution/v4/testCaseExecution"

    def to_tmf_json(self):
        payload = self._execution_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "TestCaseExecution"
        return payload

    def from_tmf_json(self, data, partial=False):
        return self._execution_from_tmf_json(data)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("testCaseExecution", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("testCaseExecution", "update", rec)
            if state_changed:
                self._notify("testCaseExecution", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="testCaseExecution",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFNonFunctionalTestExecution(models.Model):
    _name = "tmf.non.functional.test.execution"
    _description = "TMF708 NonFunctionalTestExecution"
    _inherit = ["tmf.test.execution.mixin"]

    def _get_tmf_api_path(self):
        return "/testExecution/v4/nonFunctionalTestExecution"

    def to_tmf_json(self):
        payload = self._execution_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "NonFunctionalTestExecution"
        return payload

    def from_tmf_json(self, data, partial=False):
        return self._execution_from_tmf_json(data)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("nonFunctionalTestExecution", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("nonFunctionalTestExecution", "update", rec)
            if state_changed:
                self._notify("nonFunctionalTestExecution", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="nonFunctionalTestExecution",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
