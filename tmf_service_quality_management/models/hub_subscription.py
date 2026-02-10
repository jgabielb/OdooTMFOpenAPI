# -*- coding: utf-8 -*-
import json
from odoo import models, fields


class TMF657HubSubscription(models.Model):
    _name = "tmf657.hub.subscription"
    _description = "TMF657 Hub Subscription"
    _rec_name = "callback"

    tmf_id = fields.Char(string="id", required=True, index=True)  # <-- DO NOT use 'id'
    callback = fields.Char(required=True)
    query = fields.Char()
    headers_json = fields.Text(string="headers (json)")

    _sql_constraints = [
        ("tmf657_hub_tmf_id_unique", "unique(tmf_id)", "Hub id must be unique."),
    ]

    def to_tmf_dict(self, base_path):
        self.ensure_one()
        out = {
            "id": self.tmf_id,
            "callback": self.callback,
            "query": self.query or None,
        }
        return {k: v for k, v in out.items() if v is not None}
