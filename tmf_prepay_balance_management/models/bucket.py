# -*- coding: utf-8 -*-
from odoo import models, fields, api


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

    def _tmf_payload(self):
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.type or "Bucket",
            "name": self.name,
            "status": self.status,
        }

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "BucketCreateEvent",
            "update": "BucketAttributeValueChangeEvent",
            "delete": "BucketDeleteEvent",
        }
        if payloads is None:
            payloads = [rec._tmf_payload() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("bucket", event_name, payload)
            except Exception:
                continue

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec._tmf_payload() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res

