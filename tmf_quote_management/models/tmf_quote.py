# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json


class TMFQuote(models.Model):
    _name = "tmf.quote"
    _description = "TMF648 Quote"
    _inherit = ["tmf.model.mixin"]

    # Core identifiers
    tmf_external_id = fields.Char(string="externalId", index=True)
    tmf_href = fields.Char(string="href")  # optional, can be computed

    # Business fields
    category = fields.Char()
    description = fields.Text()

    # Dates
    quote_date = fields.Datetime(string="quoteDate", required=True, default=fields.Datetime.now)
    requested_quote_completion_date = fields.Datetime(string="requestedQuoteCompletionDate")
    expected_quote_completion_date = fields.Datetime(string="expectedQuoteCompletionDate")
    effective_quote_completion_date = fields.Datetime(string="effectiveQuoteCompletionDate")
    expected_fulfillment_start_date = fields.Datetime(string="expectedFulfillmentStartDate")

    # Lifecycle
    state = fields.Selection([
        ("inProgress", "inProgress"),
        ("pending", "pending"),
        ("approved", "approved"),
        ("cancelled", "cancelled"),
        ("accepted", "accepted"),
        ("rejected", "rejected"),
    ], default="inProgress", required=True)

    version = fields.Char()

    # Relationships / arrays (store as JSON for speed; you can normalize later)
    agreement_json = fields.Text(string="agreement")          # AgreementRef[*]
    billing_account_json = fields.Text(string="billingAccount")  # BillingAccountRef[*]
    contact_medium_json = fields.Text(string="contactMedium") # ContactMedium[*]
    note_json = fields.Text(string="note")                   # Note[*]
    related_party_json = fields.Text(string="relatedParty")   # RelatedParty[*]
    poq_json = fields.Text(string="productOfferingQualification")  # POQRef[*]
    authorization_json = fields.Text(string="authorization")  # Authorization[*]
    quote_total_price_json = fields.Text(string="quoteTotalPrice") # QuotePrice[*]
    valid_for_json = fields.Text(string="validFor")           # TimePeriod

    quote_item_ids = fields.One2many("tmf.quote.item", "quote_id", string="quoteItem")

    def _get_tmf_api_path(self):
        return "/tmf-api/quoteManagement/v4"

    def _compute_href(self):
        self.ensure_one()
        rid = self.tmf_id or str(self.id)
        return f"{self._get_tmf_api_path()}/quote/{rid}"

    def to_tmf_json(self, fields_param=None):
        self.ensure_one()

        payload = {
            "id": self.tmf_id or str(self.id),
            "href": self.tmf_href or self._compute_href(),
            "category": self.category or None,
            "description": self.description or None,
            "externalId": self.tmf_external_id or None,
            "instantSyncQuote": False,
            "quoteDate": fields.Datetime.to_string(self.quote_date) if self.quote_date else None,
            "requestedQuoteCompletionDate": fields.Datetime.to_string(self.requested_quote_completion_date) if self.requested_quote_completion_date else None,
            "expectedQuoteCompletionDate": fields.Datetime.to_string(self.expected_quote_completion_date) if self.expected_quote_completion_date else None,
            "effectiveQuoteCompletionDate": fields.Datetime.to_string(self.effective_quote_completion_date) if self.effective_quote_completion_date else None,
            "expectedFulfillmentStartDate": fields.Datetime.to_string(self.expected_fulfillment_start_date) if self.expected_fulfillment_start_date else None,
            "version": self.version or None,
            "state": self.state,
            "agreement": json.loads(self.agreement_json) if self.agreement_json else [],
            "billingAccount": json.loads(self.billing_account_json) if self.billing_account_json else [],
            "contactMedium": json.loads(self.contact_medium_json) if self.contact_medium_json else [],
            "note": json.loads(self.note_json) if self.note_json else [],
            "relatedParty": json.loads(self.related_party_json) if self.related_party_json else [],
            "productOfferingQualification": json.loads(self.poq_json) if self.poq_json else [],
            "authorization": json.loads(self.authorization_json) if self.authorization_json else [],
            "quoteTotalPrice": json.loads(self.quote_total_price_json) if self.quote_total_price_json else [],
            "validFor": json.loads(self.valid_for_json) if self.valid_for_json else None,
            "quoteItem": [qi.to_tmf_json() for qi in self.quote_item_ids] or [],
            "@type": "Quote",
        }


        # Strip None values
        payload = {k: v for k, v in payload.items() if v is not None}

        # Optional first-level fields filtering (TMF "fields=")
        if fields_param:
            wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
            always = {"id", "href"}
            wanted |= always
            payload = {k: v for k, v in payload.items() if k in wanted}

        return payload
