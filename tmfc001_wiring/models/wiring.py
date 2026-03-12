from odoo import api, fields, models


def _resolve_ids(env, model, items, id_field="tmf_id"):
    """Batch-search model by tmf_id for all item dicts. Returns list of record IDs."""
    ref_ids = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("id") or "").strip()
        if ref_id:
            ref_ids.append(ref_id)
    if not ref_ids:
        return []
    return env[model].sudo().search([(id_field, "in", ref_ids)]).ids


class ProductOfferingTMFC001Wiring(models.Model):
    """TMFC001 dependent API wiring for ProductOffering (product.template)."""
    _inherit = "product.template"

    # Raw JSON storage (carries the wire-format payload for cross-API refs)
    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632/669)")
    place_json = fields.Json(default=list, string="Place refs JSON (TMF673/674/675)")
    agreement_json = fields.Json(default=list, string="Agreement refs JSON (TMF651)")
    service_specification_json = fields.Json(default=list, string="Service Spec refs JSON (TMF633)")
    resource_specification_json = fields.Json(default=list, string="Resource Spec refs JSON (TMF634)")

    # Resolved relational fields (populated by _resolve_tmf_refs)
    related_partner_ids = fields.Many2many(
        "res.partner", "tmf_offering_partner_rel",
        "offering_id", "partner_id", string="Related Parties (TMF632)"
    )
    related_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmf_offering_party_role_rel",
        "offering_id", "role_id", string="Party Roles (TMF669)"
    )
    service_specification_ids = fields.Many2many(
        "tmf.service.specification", "tmf_offering_service_spec_rel",
        "offering_id", "spec_id", string="Service Specifications (TMF633)"
    )
    resource_specification_ids = fields.Many2many(
        "tmf.resource.specification", "tmf_offering_resource_spec_rel",
        "offering_id", "spec_id", string="Resource Specifications (TMF634)"
    )
    agreement_ids = fields.Many2many(
        "tmf.agreement", "tmf_offering_agreement_rel",
        "offering_id", "agreement_id", string="Agreements (TMF651)"
    )
    geographic_address_id = fields.Many2one(
        "tmf.geographic.address", string="Geographic Address (TMF673)",
        index=True, ondelete="set null"
    )
    geographic_site_id = fields.Many2one(
        "tmf.geographic.site", string="Geographic Site (TMF674)",
        index=True, ondelete="set null"
    )
    geographic_location_id = fields.Many2one(
        "tmf.geographic.location", string="Geographic Location (TMF675)",
        index=True, ondelete="set null"
    )

    def _resolve_tmf_refs(self):
        """Resolve TMF JSON reference IDs to local Odoo records."""
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            # TMF632 relatedParty → res.partner (exclude PartyRole entries)
            if not rec.related_partner_ids and rec.related_party_json:
                items = [i for i in (rec.related_party_json or [])
                         if isinstance(i, dict) and i.get("@type") not in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "res.partner", items)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            # TMF669 partyRole → tmf.party.role
            if not rec.related_party_role_ids and rec.related_party_json:
                items = [i for i in (rec.related_party_json or [])
                         if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["related_party_role_ids"] = [(6, 0, ids)]

            # TMF633 serviceSpecification → tmf.service.specification
            if not rec.service_specification_ids and rec.service_specification_json:
                ids = _resolve_ids(self.env, "tmf.service.specification", rec.service_specification_json)
                if ids:
                    updates["service_specification_ids"] = [(6, 0, ids)]

            # TMF634 resourceSpecification → tmf.resource.specification
            if not rec.resource_specification_ids and rec.resource_specification_json:
                ids = _resolve_ids(self.env, "tmf.resource.specification", rec.resource_specification_json)
                if ids:
                    updates["resource_specification_ids"] = [(6, 0, ids)]

            # TMF651 agreement → tmf.agreement
            if not rec.agreement_ids and rec.agreement_json:
                ids = _resolve_ids(self.env, "tmf.agreement", rec.agreement_json)
                if ids:
                    updates["agreement_ids"] = [(6, 0, ids)]

            # TMF673/674/675 place → geographic models — batch by type then assign first match
            if rec.place_json and not all([rec.geographic_address_id, rec.geographic_site_id, rec.geographic_location_id]):
                addr_ids, site_ids, loc_ids = [], [], []
                for item in (rec.place_json or []):
                    if not isinstance(item, dict):
                        continue
                    ref_id = str(item.get("id") or "").strip()
                    if not ref_id:
                        continue
                    at_type = item.get("@type", "")
                    if at_type in ("GeographicAddress", "GeographicAddressRef"):
                        addr_ids.append(ref_id)
                    elif at_type in ("GeographicSite", "GeographicSiteRef"):
                        site_ids.append(ref_id)
                    elif at_type in ("GeographicLocation", "GeographicLocationRef"):
                        loc_ids.append(ref_id)

                if addr_ids and not rec.geographic_address_id:
                    match = self.env["tmf.geographic.address"].sudo().search([("tmf_id", "in", addr_ids)], limit=1)
                    if match:
                        updates["geographic_address_id"] = match.id
                if site_ids and not rec.geographic_site_id:
                    match = self.env["tmf.geographic.site"].sudo().search([("tmf_id", "in", site_ids)], limit=1)
                    if match:
                        updates["geographic_site_id"] = match.id
                if loc_ids and not rec.geographic_location_id:
                    match = self.env["tmf.geographic.location"].sudo().search([("tmf_id", "in", loc_ids)], limit=1)
                    if match:
                        updates["geographic_location_id"] = match.id

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {
                "related_party_json", "place_json", "agreement_json",
                "service_specification_json", "resource_specification_json",
            }
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res


class ProductSpecificationTMFC001Wiring(models.Model):
    """TMFC001 dependent API wiring for ProductSpecification (tmf.product.specification)."""
    _inherit = "tmf.product.specification"

    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    service_specification_json = fields.Json(default=list, string="Service Spec refs JSON (TMF633)")
    resource_specification_json = fields.Json(default=list, string="Resource Spec refs JSON (TMF634)")

    related_partner_ids = fields.Many2many(
        "res.partner", "tmf_product_spec_partner_rel",
        "spec_id", "partner_id", string="Related Parties (TMF632)"
    )
    service_specification_ids = fields.Many2many(
        "tmf.service.specification", "tmf_product_spec_service_spec_rel",
        "spec_id", "svc_id", string="Service Specifications (TMF633)"
    )
    resource_specification_ids = fields.Many2many(
        "tmf.resource.specification", "tmf_product_spec_resource_spec_rel",
        "spec_id", "res_id", string="Resource Specifications (TMF634)"
    )

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            if not rec.related_partner_ids and rec.related_party_json:
                ids = _resolve_ids(self.env, "res.partner", rec.related_party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            if not rec.service_specification_ids and rec.service_specification_json:
                ids = _resolve_ids(self.env, "tmf.service.specification", rec.service_specification_json)
                if ids:
                    updates["service_specification_ids"] = [(6, 0, ids)]

            if not rec.resource_specification_ids and rec.resource_specification_json:
                ids = _resolve_ids(self.env, "tmf.resource.specification", rec.resource_specification_json)
                if ids:
                    updates["resource_specification_ids"] = [(6, 0, ids)]

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {"related_party_json", "service_specification_json", "resource_specification_json"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res
