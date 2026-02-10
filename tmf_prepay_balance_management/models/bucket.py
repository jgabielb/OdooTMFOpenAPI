# -*- coding: utf-8 -*-
from odoo import models, fields


class TMF654Bucket(models.Model):
    _name = "tmf654.bucket"
    _description = "TMF654 Bucket"
    _rec_name = "name"

    # TMF common
    tmf_id = fields.Char(string="id", required=True, index=True)
    href = fields.Char()
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    type = fields.Char(string="@type", default="Bucket")

    description = fields.Char()
    name = fields.Char()
    is_shared = fields.Boolean(string="isShared", default=False)

    usage_type = fields.Char(string="usageType", required=True)  # data/voice/monetary/etc.
    status = fields.Char()  # active/expired/suspended

    remaining_amount = fields.Float()
    remaining_units = fields.Char()
    remaining_value_name = fields.Char(string="remainingValueName")

    requested_date = fields.Datetime(string="requestedDate")
    confirmation_date = fields.Datetime(string="confirmationDate")

    reserved_amount = fields.Float()
    reserved_units = fields.Char()

    valid_for_start = fields.Datetime()
    valid_for_end = fields.Datetime()

    party_account_json = fields.Text(string="partyAccount")
    product_json = fields.Text(string="product")
    logical_resource_json = fields.Text(string="logicalResource")
    related_party_json = fields.Text(string="relatedParty")

