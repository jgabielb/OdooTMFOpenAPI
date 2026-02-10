# -*- coding: utf-8 -*-
from odoo import models, fields
from datetime import datetime, timezone

API_BASE = "/tmf-api/agreementManagement/v4"


class TMFAgreement(models.Model):
    _name = "tmf.agreement"
    _description = "Agreement"
    _inherit = ["tmf.model.mixin"]

    # ---------
    # Core fields (TMF651 Agreement)
    # ---------
    name = fields.Char(required=True)
    agreement_type = fields.Char(required=True)  # agreementType (mandatory on create)
    status = fields.Char()
    description = fields.Char()
    statement_of_intent = fields.Char()
    version = fields.Char(default="0")  # spec default when creating: 0
    document_number = fields.Integer()

    initial_date = fields.Datetime()
    completion_date = fields.Char()  # spec says Date at which completed; keep as ISO string if you want

    # Complex structures from TMF payloads (arrays/objects) → keep as JSON
    agreement_authorization = fields.Json()
    agreement_item = fields.Json(required=True)          # agreementItem (mandatory on create)
    agreement_period = fields.Json()
    agreement_specification = fields.Json()
    associated_agreement = fields.Json()
    characteristic = fields.Json()
    engaged_party = fields.Json(required=True)           # engagedParty (mandatory on create)

    def _get_tmf_api_path(self):
        # TMF651 Agreement resource path
        return f"{API_BASE}/agreement"

    def _ensure_defaults(self):
        """Apply defaults described in TMF651 for create behavior."""
        if not self.completion_date:
            self.completion_date = datetime.now(timezone.utc).isoformat()
        if not self.version:
            self.version = "0"

    def create(self, vals_list):
        records = super().create(vals_list)
        for r in records:
            r._ensure_defaults()
        return records

    def to_tmf_json(self):
        self.ensure_one()
        tmf_id = self.tmf_id or str(self.id)
        href = f"{API_BASE}/agreement/{tmf_id}"

        return {
            "id": tmf_id,
            "href": href,
            "@type": "Agreement",
            "name": self.name,
            "agreementType": self.agreement_type,
            "status": self.status,
            "description": self.description,
            "statementOfIntent": self.statement_of_intent,
            "version": self.version,
            "documentNumber": self.document_number,
            "initialDate": self.initial_date.isoformat() if self.initial_date else None,
            "completionDate": self.completion_date,
            "agreementAuthorization": self.agreement_authorization,
            "agreementItem": self.agreement_item,
            "agreementPeriod": self.agreement_period,
            "agreementSpecification": self.agreement_specification,
            "associatedAgreement": self.associated_agreement,
            "characteristic": self.characteristic,
            "engagedParty": self.engaged_party,
        }


class TMFAgreementSpecification(models.Model):
    _name = "tmf.agreement.specification"
    _description = "AgreementSpecification"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(required=True)
    description = fields.Char()
    is_bundle = fields.Boolean(default=False)
    last_update = fields.Datetime()
    lifecycle_status = fields.Char()
    version = fields.Char()

    # TMF651: attachment is mandatory on create
    attachment = fields.Json(required=True)
    related_party = fields.Json()
    service_category = fields.Json()
    specification_characteristic = fields.Json()
    specification_relationship = fields.Json()
    valid_for = fields.Json()

    def _get_tmf_api_path(self):
        return f"{API_BASE}/agreementSpecification"

    def to_tmf_json(self):
        self.ensure_one()
        tmf_id = self.tmf_id or str(self.id)
        href = f"{API_BASE}/agreementSpecification/{tmf_id}"
        return {
            "id": tmf_id,
            "href": href,
            "@type": "AgreementSpecification",
            "name": self.name,
            "description": self.description,
            "isBundle": self.is_bundle,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status,
            "version": self.version,
            "attachment": self.attachment,
            "relatedParty": self.related_party,
            "serviceCategory": self.service_category,
            "specificationCharacteristic": self.specification_characteristic,
            "specificationRelationship": self.specification_relationship,
            "validFor": self.valid_for,
        }
