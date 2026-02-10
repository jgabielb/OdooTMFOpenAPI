# -*- coding: utf-8 -*-
from odoo import models, fields


class TMF654TransferBalance(models.Model):
    _name = "tmf654.transfer.balance"
    _description = "TMF654 TransferBalance"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(string="id", required=True, index=True)
    href = fields.Char()
    type = fields.Char(string="@type", default="TransferBalance")

    description = fields.Char()
    reason = fields.Char()
    status = fields.Char()
    usage_type = fields.Char(string="usageType")

    requested_date = fields.Datetime()
    confirmation_date = fields.Datetime()

    cost_owner = fields.Char(string="costOwner")  # originator/receiver 
    transfer_cost_value = fields.Float()
    transfer_cost_units = fields.Char()

    amount_value = fields.Float()
    amount_units = fields.Char()

    # source refs
    bucket_json = fields.Text(string="bucket")
    party_account_json = fields.Text(string="partyAccount")
    product_json = fields.Text(string="product")
    logical_resource_json = fields.Text(string="logicalResource")
    related_party_json = fields.Text(string="relatedParty")

    # receiver refs
    receiver_json = fields.Text(string="receiver")
    receiver_bucket_json = fields.Text(string="receiverBucket")
    receiver_party_account_json = fields.Text(string="receiverPartyAccount")
    receiver_product_json = fields.Text(string="receiverProduct")
    receiver_logical_resource_json = fields.Text(string="receiverLogicalResource")
    receiver_bucket_usage_type = fields.Char(string="receiverBucketUsageType")

    channel_json = fields.Text(string="channel")
    impacted_bucket_json = fields.Text(string="impactedBucket")
    requestor_json = fields.Text(string="requestor")
