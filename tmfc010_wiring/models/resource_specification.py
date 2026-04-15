# -*- coding: utf-8 -*-
from odoo import fields, models


class TMFC010ResourceSpecification(models.Model):
    _inherit = "tmf.resource.specification"

    tmfc010_related_party_json = fields.Json(
        string="TMFC010 RelatedParty (raw)",
        help="Raw TMF632/TMF669 relatedParty fragment from TMF634 resourceSpecification payload.",
    )
    tmfc010_resource_spec_rel_json = fields.Json(
        string="TMFC010 ResourceSpec Relationship (raw)",
        help="Raw TMF634 resourceSpecRelationship fragment for peer resource specifications.",
    )
    tmfc010_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc010_resource_spec_partner_rel",
        column1="resource_spec_id",
        column2="partner_id",
        string="TMFC010 Related Partners",
    )
    tmfc010_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc010_resource_spec_party_role_rel",
        column1="resource_spec_id",
        column2="party_role_id",
        string="TMFC010 Party Roles",
    )
    tmfc010_related_spec_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        relation="tmfc010_resource_spec_related_rel",
        column1="src_spec_id",
        column2="dst_spec_id",
        string="TMFC010 Related Resource Specifications",
    )
