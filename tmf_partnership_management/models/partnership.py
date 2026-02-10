# -*- coding: utf-8 -*-
from odoo import models, fields


class TMFPartnership(models.Model):
    _name = "tmf.partnership"
    _description = "TMF668 Partnership"
    _rec_name = "name"

    tmf_id = fields.Char(string="TMF id", index=True, required=True)
    href = fields.Char(string="href", index=True)
    name = fields.Char(required=True)
    description = fields.Text()

    specification_json = fields.Text(string="specification")  # ref object as JSON string
    partner_json = fields.Text(string="partner")              # list as JSON string

    _sql_constraints = [
        ("tmf_id_unique", "unique(tmf_id)", "TMF id must be unique."),
    ]
