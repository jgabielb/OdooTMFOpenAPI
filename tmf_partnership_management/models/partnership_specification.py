# -*- coding: utf-8 -*-
from odoo import models, fields


class TMFPartnershipSpecification(models.Model):
    _name = "tmf.partnership.specification"
    _description = "TMF668 PartnershipSpecification"
    _rec_name = "name"

    tmf_id = fields.Char(string="TMF id", index=True, required=True)
    href = fields.Char(string="href", index=True)
    name = fields.Char(required=True)
    description = fields.Text()
    role_specification_json = fields.Text(string="roleSpecification")  # list of objects as JSON string

    _sql_constraints = [
        ("tmf_id_unique", "unique(tmf_id)", "TMF id must be unique."),
    ]
