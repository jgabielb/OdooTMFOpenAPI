# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TMFC006WiringTools(models.AbstractModel):
    _name = "tmfc006.wiring.tools"
    _description = "TMFC006 Wiring Tools - Service Catalog foundational wiring"

    # Minimal JSON reference fields for TMF634/TMF632/TMF669/TMF662 payload fragments
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

    # Relational stubs: we only add these where base models exist and are already TMF-backed
    related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Related Partners",
        help="Resolved TMF632 individuals/organizations referenced from serviceSpecification.relatedParty.",
    )
    party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        string="Party Roles",
        help="Resolved TMF669 partyRoles linked to the service specification.",
    )
    resource_specification_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        string="Resource Specifications",
        help="Resolved TMF634 resourceSpecification records used by this service specification.",
    )
    entity_specification_ids = fields.Many2many(
        comodel_name="tmf.entity.specification",
        string="Entity Specifications",
        help="Resolved TMF662 entitySpecification records used by this service specification.",
    )

    @api.model
    def _resolve_service_spec_references(self, vals_list):
        """Best-effort resolution helper used from TMF633 flows.

        This is intentionally conservative for pass 1:
        - it expects `tmf_id` fields in incoming payload fragments
        - it avoids creating any TMF master-data records
        - it can be safely called from controllers/models via context flag
        """
        # Placeholder for future implementation once we have concrete payload examples.
        # Pass 1 focuses on establishing the model surface so other components can call into it.
        return vals_list

    @api.model
    def _handle_resource_catalog_event(self, payload):
        """Entry point for TMF634 callbacks.

        Pass 1 only logs payload shape or performs no-ops, keeping URLs stable while
        deferring concrete reconciliation rules to a later iteration.
        """
        # Intentionally minimal; actual reconciliation will be introduced in a later pass
        return True

    @api.model
    def _handle_entity_catalog_event(self, payload):
        """Entry point for TMF662 callbacks.

        Similar to `_handle_resource_catalog_event`, this is scaffolding that allows
        controllers to route events without yet mutating Service Catalog records.
        """
        return True
