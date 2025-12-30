from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.party.privacy.agreement'
    _description = 'PartyPrivacyAgreement'
    _inherit = ['tmf.model.mixin']

    agreement_type = fields.Char(string="agreementType", help="The type of the agreement. For example commercial")
    description = fields.Char(string="description", help="Narrative that explains the agreement and details about the it , such as why the agreement is taking")
    document_number = fields.Integer(string="documentNumber", help="A reference number assigned to an Agreement that follows a prescribed numbering system.")
    initial_date = fields.Datetime(string="initialDate", help="Date at which the agreement was initialized")
    name = fields.Char(string="name", help="A human-readable name for the agreement")
    statement_of_intent = fields.Char(string="statementOfIntent", help="An overview and goals of the Agreement")
    status = fields.Char(string="status", help="The current status of the agreement. Typical values are: in process, approved and rejected")
    version = fields.Char(string="version", help="A string identifying the version of the agreement")
    agreement_authorization = fields.Char(string="agreementAuthorization", help="")
    agreement_item = fields.Char(string="agreementItem", help="")
    agreement_period = fields.Char(string="agreementPeriod", help="The time period during which the Agreement is in effect.")
    agreement_specification = fields.Char(string="agreementSpecification", help="")
    associated_agreement = fields.Char(string="associatedAgreement", help="")
    characteristic = fields.Char(string="characteristic", help="")
    completion_date = fields.Char(string="completionDate", help="Date at which the agreement is completed")
    engaged_party = fields.Char(string="engagedParty", help="")
    party_privacy_profile = fields.Char(string="partyPrivacyProfile", help="The privacy profiles that are the subject of the agreement")
    party_privacy_profile_characteristic = fields.Char(string="partyPrivacyProfileCharacteristic", help="A list of (typically) high criticality characteristics whose chosen privacy rules are included in th")

    def _get_tmf_api_path(self):
        return "/party_privacy_agreementManagement/v4/PartyPrivacyAgreement"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "PartyPrivacyAgreement",
            "agreementType": self.agreement_type,
            "description": self.description,
            "documentNumber": self.document_number,
            "initialDate": self.initial_date.isoformat() if self.initial_date else None,
            "name": self.name,
            "statementOfIntent": self.statement_of_intent,
            "status": self.status,
            "version": self.version,
            "agreementAuthorization": self.agreement_authorization,
            "agreementItem": self.agreement_item,
            "agreementPeriod": self.agreement_period,
            "agreementSpecification": self.agreement_specification,
            "associatedAgreement": self.associated_agreement,
            "characteristic": self.characteristic,
            "completionDate": self.completion_date,
            "engagedParty": self.engaged_party,
            "partyPrivacyProfile": self.party_privacy_profile,
            "partyPrivacyProfileCharacteristic": self.party_privacy_profile_characteristic,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('partyPrivacyAgreement', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('partyPrivacyAgreement', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='partyPrivacyAgreement',
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
