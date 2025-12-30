from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.party.role.product.offering.risk.assessment'
    _description = 'PartyRoleProductOfferingRiskAssessment'
    _inherit = ['tmf.model.mixin']

    status = fields.Char(string="status", help="The status of the risk assessment, such as Succeeded, In Progress, Failed, output from the task")
    characteristic = fields.Char(string="characteristic", help="Additional characteristics for which the risk might be assessed, optional input to the task")
    party_role = fields.Char(string="partyRole", help="The party or party role for which the assessment is to be carried out, must be supplied as input to ")
    place = fields.Char(string="place", help="The place for which the risk is assessed, this is optional input to the task")
    product_offering = fields.Char(string="productOffering", help="The product offering for which the assessment is to be carried out, must be supplied as input to the")
    risk_assessment_result = fields.Char(string="riskAssessmentResult", help="The result of the risk assessment, output from the task")

    def _get_tmf_api_path(self):
        return "/party_role_product_offering_risk_assessmentManagement/v4/PartyRoleProductOfferingRiskAssessment"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "PartyRoleProductOfferingRiskAssessment",
            "status": self.status,
            "characteristic": self.characteristic,
            "partyRole": self.party_role,
            "place": self.place,
            "productOffering": self.product_offering,
            "riskAssessmentResult": self.risk_assessment_result,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('partyRoleProductOfferingRiskAssessment', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('partyRoleProductOfferingRiskAssessment', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='partyRoleProductOfferingRiskAssessment',
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
