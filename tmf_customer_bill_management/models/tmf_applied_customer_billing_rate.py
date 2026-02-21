# -*- coding: utf-8 -*-
import uuid
from odoo import fields, models


class TMFAppliedCustomerBillingRate(models.Model):
    _name = "tmf.applied.customer.billing.rate"
    _description = "TMF678 AppliedCustomerBillingRate"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)
    tmf_type = fields.Char(required=True, default="AppliedCustomerBillingRate")  # @type

    date = fields.Datetime(index=True)  # mandatory in conformance tables (when present rules)
    is_billed = fields.Boolean(default=False)  # isBilled
    payload = fields.Json(string="TMF Payload")

    last_update = fields.Datetime(index=True, default=fields.Datetime.now)

    def _compute_href(self, host_url: str, api_base: str):
        host_url = (host_url or "").rstrip("/")
        return f"{host_url}{api_base}/appliedCustomerBillingRate/{self.tmf_id}"