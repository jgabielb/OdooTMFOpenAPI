# -*- coding: utf-8 -*-
from odoo import models, fields


class TMF654TopupBalance(models.Model):
    _name = "tmf654.topup.balance"
    _description = "TMF654 TopupBalance"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(string="id", required=True, index=True)
    href = fields.Char()
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    type = fields.Char(string="@type", default="TopupBalance")

    description = fields.Char()
    reason = fields.Char()
    status = fields.Char()  # requested/confirmed/cancelled/failed (implementation-defined)
    usage_type = fields.Char(string="usageType")

    requested_date = fields.Datetime()
    confirmation_date = fields.Datetime()

    # amount
    amount_value = fields.Float()
    amount_units = fields.Char()

    is_auto_topup = fields.Boolean(string="isAutoTopup", default=False)
    number_of_periods = fields.Integer(string="numberOfPeriods")
    recurring_period = fields.Char(string="recurringPeriod")
    voucher = fields.Char()

    # references as JSON
    bucket_json = fields.Text(string="bucket")
    impacted_bucket_json = fields.Text(string="impactedBucket")
    channel_json = fields.Text(string="channel")
    payment_json = fields.Text(string="payment")
    payment_method_json = fields.Text(string="paymentMethod")
    party_account_json = fields.Text(string="partyAccount")
    product_json = fields.Text(string="product")
    logical_resource_json = fields.Text(string="logicalResource")
    related_party_json = fields.Text(string="relatedParty")
    requestor_json = fields.Text(string="requestor")
