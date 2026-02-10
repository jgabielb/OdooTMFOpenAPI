# -*- coding: utf-8 -*-
from odoo import models, fields


class TMF654AdjustBalance(models.Model):
    _name = "tmf654.adjust.balance"
    _description = "TMF654 AdjustBalance"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(string="id", required=True, index=True)
    href = fields.Char()
    type = fields.Char(string="@type", default="AdjustBalance")

    description = fields.Char()
    reason = fields.Char()
    status = fields.Char()
    usage_type = fields.Char(string="usageType")

    requested_date = fields.Datetime()
    confirmation_date = fields.Datetime()

    adjust_type = fields.Char(string="adjustType")  # spec has values like oneTimeChargeCredit/debit etc. 

    amount_value = fields.Float()
    amount_units = fields.Char()

    bucket_json = fields.Text(string="bucket")
    impacted_bucket_json = fields.Text(string="impactedBucket")
    channel_json = fields.Text(string="channel")
    party_account_json = fields.Text(string="partyAccount")
    product_json = fields.Text(string="product")
    logical_resource_json = fields.Text(string="logicalResource")
    related_party_json = fields.Text(string="relatedParty")
    requestor_json = fields.Text(string="requestor")
