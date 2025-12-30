from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.test.scenario'
    _description = 'TestScenario'
    _inherit = ['tmf.model.mixin']

    description = fields.Char(string="description", help="The description for the artifact")
    version = fields.Char(string="version", help="The artifact version")
    version_description = fields.Char(string="versionDescription", help="The artifact version description")
    agreement = fields.Char(string="agreement", help="")
    attribute = fields.Char(string="attribute", help="")
    related_party = fields.Char(string="relatedParty", help="")
    state = fields.Char(string="state", help="")
    test_scenario_definition = fields.Char(string="testScenarioDefinition", help="")

    def _get_tmf_api_path(self):
        return "/test_scenarioManagement/v4/TestScenario"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "TestScenario",
            "description": self.description,
            "version": self.version,
            "versionDescription": self.version_description,
            "agreement": self.agreement,
            "attribute": self.attribute,
            "relatedParty": self.related_party,
            "state": self.state,
            "testScenarioDefinition": self.test_scenario_definition,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('testScenario', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('testScenario', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='testScenario',
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
