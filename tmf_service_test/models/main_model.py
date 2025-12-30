from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.service.test'
    _description = 'ServiceTest'
    _inherit = ['tmf.model.mixin']

    description = fields.Char(string="description", help="Description of the service test")
    end_date_time = fields.Datetime(string="endDateTime", help="The end date and time of the service test")
    mode = fields.Char(string="mode", help="An indication of whether the service test is running in 'PROACTIVE' or 'ONDEMAND' mode")
    name = fields.Char(string="name", help="The name of the service test")
    start_date_time = fields.Datetime(string="startDateTime", help="The start date and time of the service test.")
    state = fields.Char(string="state", help="The actual state the service test is in")
    characteristic = fields.Char(string="characteristic", help="List of characteristics with values that define the test run")
    related_party = fields.Char(string="relatedParty", help="Party related to the test")
    related_service = fields.Char(string="relatedService", help="The actual service being tested")
    test_measure = fields.Char(string="testMeasure", help="The results of the test in terms of the measured metrics")
    test_specification = fields.Char(string="testSpecification", help="The specification for this test")
    valid_for = fields.Char(string="validFor", help="The validity time for the test results")

    def _get_tmf_api_path(self):
        return "/service_testManagement/v4/ServiceTest"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ServiceTest",
            "description": self.description,
            "endDateTime": self.end_date_time.isoformat() if self.end_date_time else None,
            "mode": self.mode,
            "name": self.name,
            "startDateTime": self.start_date_time.isoformat() if self.start_date_time else None,
            "state": self.state,
            "characteristic": self.characteristic,
            "relatedParty": self.related_party,
            "relatedService": self.related_service,
            "testMeasure": self.test_measure,
            "testSpecification": self.test_specification,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('serviceTest', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('serviceTest', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceTest',
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
