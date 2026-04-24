# -*- coding: utf-8 -*-
from odoo import models, fields


class TMF668HubSubscription(models.Model):
    _name = "tmf668.hub.subscription"
    _description = "TMF668 Hub Subscription"

    tmf_id = fields.Char(string="id", required=True, index=True)
    callback = fields.Char(required=True)
    query = fields.Char()

    _tmf_id_unique = models.Constraint("unique(tmf_id)", "Hub id must be unique.")
