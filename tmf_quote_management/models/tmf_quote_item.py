# -*- coding: utf-8 -*-
from odoo import models, fields
import json


class TMFQuoteItem(models.Model):
    _name = "tmf.quote.item"
    _description = "TMF648 QuoteItem"

    quote_id = fields.Many2one("tmf.quote", required=True, ondelete="cascade")

    item_id = fields.Char(string="id", required=True)  # sequence-like
    action = fields.Char()
    quantity = fields.Integer(default=1)

    state = fields.Char()  # should NOT be set in POST (rule enforced in controller)
    # Store complex substructures as JSON
    product_json = fields.Text(string="product")                 # ProductRefOrValue
    product_offering_json = fields.Text(string="productOffering") # ProductOfferingRef
    attachment_json = fields.Text(string="attachment")           # AttachmentRefOrValue[*]
    note_json = fields.Text(string="note")                       # Note[*]
    related_party_json = fields.Text(string="relatedParty")      # RelatedParty[*]
    appointment_json = fields.Text(string="appointment")         # AppointmentRef[*]
    quote_item_price_json = fields.Text(string="quoteItemPrice") # QuotePrice[*] (not in POST)
    quote_item_auth_json = fields.Text(string="quoteItemAuthorization")  # Authorization[*] (not in POST)
    quote_item_rel_json = fields.Text(string="quoteItemRelationship")    # QuoteItemRelationship[*]
    embedded_quote_item_json = fields.Text(string="quoteItem")   # QuoteItem[*] nested

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.item_id,
            "action": self.action or None,
            "quantity": self.quantity or 1,
            "state": self.state or None,
            "product": json.loads(self.product_json) if self.product_json else None,
            "productOffering": json.loads(self.product_offering_json) if self.product_offering_json else None,
            "attachment": json.loads(self.attachment_json) if self.attachment_json else [],
            "note": json.loads(self.note_json) if self.note_json else [],
            "relatedParty": json.loads(self.related_party_json) if self.related_party_json else [],
            "appointment": json.loads(self.appointment_json) if self.appointment_json else [],
            "quoteItemPrice": json.loads(self.quote_item_price_json) if self.quote_item_price_json else None,
            "quoteItemAuthorization": json.loads(self.quote_item_auth_json) if self.quote_item_auth_json else None,
            "quoteItemRelationship": json.loads(self.quote_item_rel_json) if self.quote_item_rel_json else [],
            "quoteItem": json.loads(self.embedded_quote_item_json) if self.embedded_quote_item_json else [],
            "@type": "QuoteItem",
        }
        return {k: v for k, v in payload.items() if v is not None}
