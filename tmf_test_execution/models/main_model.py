from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.test.execution'
    _description = 'TestExecution'
    _inherit = ['tmf.model.mixin']

    data_correlation_id = fields.Char(string="dataCorrelationId", help="Data correlation ID passed in by the API consumer")
    general_test_artifact = fields.Char(string="generalTestArtifact", help="")
    state = fields.Char(string="state", help="")
    test_data_instance = fields.Char(string="testDataInstance", help="")
    test_environment_provisioning_execution = fields.Char(string="testEnvironmentProvisioningExecution", help="")

    def _get_tmf_api_path(self):
        return "/test_executionManagement/v4/TestExecution"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "TestExecution",
            "dataCorrelationId": self.data_correlation_id,
            "generalTestArtifact": self.general_test_artifact,
            "state": self.state,
            "testDataInstance": self.test_data_instance,
            "testEnvironmentProvisioningExecution": self.test_environment_provisioning_execution,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('testExecution', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('testExecution', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='testExecution',
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
