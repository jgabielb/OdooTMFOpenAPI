# -*- coding: utf-8 -*-
from odoo import fields, models


class TMFC006ServiceSpecification(models.Model):
    """TMFC006 side-car fields on tmf.service.specification.

    These fields were previously declared on the ``tmfc006.wiring.tools``
    AbstractModel, which meant they were never materialized on real records
    and the feature-detection in ``tmf_service_catalog`` always skipped
    them. Moving them to an ``_inherit`` model makes the TMFC006 wiring
    actually persist TMF634/TMF632/TMF669/TMF662 reference fragments and
    their resolved relational links.
    """

    _inherit = "tmf.service.specification"

    service_spec_related_party_json = fields.Json(
        string="Service Spec RelatedParty (raw)",
        help="Raw TMF632/TMF669 relatedParty fragment from TMF633 serviceSpecification payload.",
    )
    service_spec_resource_spec_json = fields.Json(
        string="Service Spec ResourceSpecification (raw)",
        help="Raw TMF634 resourceSpecification fragment from TMF633 serviceSpecification payload.",
    )
    service_spec_entity_spec_json = fields.Json(
        string="Service Spec EntitySpecification (raw)",
        help="Raw TMF662 entitySpecification/associationSpecification fragment from TMF633 serviceSpecification payload.",
    )

    related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc006_service_spec_partner_rel",
        column1="service_spec_id",
        column2="partner_id",
        string="Related Partners",
        help="Resolved TMF632 individuals/organizations referenced from serviceSpecification.relatedParty.",
    )
    party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc006_service_spec_party_role_rel",
        column1="service_spec_id",
        column2="party_role_id",
        string="Party Roles",
        help="Resolved TMF669 partyRoles linked to the service specification.",
    )
    resource_specification_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        relation="tmfc006_service_spec_resource_spec_rel",
        column1="service_spec_id",
        column2="resource_spec_id",
        string="Resource Specifications",
        help="Resolved TMF634 resourceSpecification records used by this service specification.",
    )
    entity_specification_ids = fields.Many2many(
        comodel_name="tmf.entity.specification",
        relation="tmfc006_service_spec_entity_spec_rel",
        column1="service_spec_id",
        column2="entity_spec_id",
        string="Entity Specifications",
        help="Resolved TMF662 entitySpecification records used by this service specification.",
    )
