from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.product.offering.qualification'
    _description = 'ProductOfferingQualification'
    _inherit = ['tmf.model.mixin']

    effective_qualification_date = fields.Datetime(string="effectiveQualificationDate", help="Effective date to productOfferingQualification completion")
    expected_poq_completion_date = fields.Datetime(string="expectedPOQCompletionDate", help="Date when the requester expect to provide an answer for the qualification request")
    instant_sync_qualification = fields.Boolean(string="instantSyncQualification", help="An indicator which when the value is 'true' means that requester expects to get qualifcation result ")
    project_id = fields.Char(string="projectId", help="This value MAY be assigned by the Buyer/Seller to identify a project the serviceability request is a")
    provide_alternative = fields.Boolean(string="provideAlternative", help="An indicator which when the value is 'true' means that alternative solutions should be provided")
    requested_poq_completion_date = fields.Datetime(string="requestedPOQCompletionDate", help="Deadline date when the requester expected a qualification answer")
    product_offering_qualification_item = fields.Char(string="productOfferingQualificationItem", help="Qualification item for a product or a category")
    related_party = fields.Char(string="relatedParty", help="Party playing a role for this qualification (as requester for example)")
    state = fields.Char(string="state", help="State of the productOfferingQualification defined in the state engine")
    state_change = fields.Char(string="stateChange", help="State change for the POQ")

    def _get_tmf_api_path(self):
        return "/product_offering_qualificationManagement/v4/ProductOfferingQualification"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ProductOfferingQualification",
            "effectiveQualificationDate": self.effective_qualification_date.isoformat() if self.effective_qualification_date else None,
            "expectedPOQCompletionDate": self.expected_poq_completion_date.isoformat() if self.expected_poq_completion_date else None,
            "instantSyncQualification": self.instant_sync_qualification,
            "projectId": self.project_id,
            "provideAlternative": self.provide_alternative,
            "requestedPOQCompletionDate": self.requested_poq_completion_date.isoformat() if self.requested_poq_completion_date else None,
            "productOfferingQualificationItem": self.product_offering_qualification_item,
            "relatedParty": self.related_party,
            "state": self.state,
            "stateChange": self.state_change,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('productOfferingQualification', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('productOfferingQualification', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOfferingQualification',
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
