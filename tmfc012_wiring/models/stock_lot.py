# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models


def _loads(value):
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


class TMFC012StockLot(models.Model):
    _inherit = "stock.lot"

    tmfc012_resource_spec_ref_json = fields.Json(
        string="TMFC012 ResourceSpecification Ref (raw)",
    )
    tmfc012_resource_specification_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        relation="tmfc012_stock_lot_resource_spec_rel",
        column1="lot_id",
        column2="resource_spec_id",
        string="TMFC012 Resource Specifications",
    )
    tmfc012_related_party_json = fields.Json(
        string="TMFC012 RelatedParty (raw)",
    )
    tmfc012_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc012_stock_lot_partner_rel",
        column1="lot_id",
        column2="partner_id",
        string="TMFC012 Related Partners",
    )
    tmfc012_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc012_stock_lot_party_role_rel",
        column1="lot_id",
        column2="party_role_id",
        string="TMFC012 Party Roles",
    )
    tmfc012_place_ref_json = fields.Json(
        string="TMFC012 Place Ref (raw)",
    )
    tmfc012_geographic_address_ids = fields.Many2many(
        comodel_name="tmf.geographic.address",
        relation="tmfc012_stock_lot_geo_address_rel",
        column1="lot_id",
        column2="address_id",
        string="TMFC012 Geographic Addresses",
    )
    tmfc012_geographic_site_ids = fields.Many2many(
        comodel_name="tmf.geographic.site",
        relation="tmfc012_stock_lot_geo_site_rel",
        column1="lot_id",
        column2="site_id",
        string="TMFC012 Geographic Sites",
    )
    tmfc012_geographic_location_ids = fields.Many2many(
        comodel_name="tmf.geographic.location",
        relation="tmfc012_stock_lot_geo_location_rel",
        column1="lot_id",
        column2="location_id",
        string="TMFC012 Geographic Locations",
    )

    def _tmfc012_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            spec_items = _loads(rec.tmfc012_resource_spec_ref_json) or []
            if isinstance(spec_items, dict):
                spec_items = [spec_items]
            spec_refs = [
                str(i.get("id") or "").strip()
                for i in spec_items if isinstance(i, dict) and i.get("id")
            ]
            if spec_refs:
                specs = self.env["tmf.resource.specification"].sudo().search(
                    [("tmf_id", "in", spec_refs)]
                )
                if specs:
                    updates["tmfc012_resource_specification_ids"] = [(6, 0, specs.ids)]

            party_items = _loads(rec.tmfc012_related_party_json) or []
            party_refs, role_refs = [], []
            for it in party_items:
                if not isinstance(it, dict):
                    continue
                ref_id = str(it.get("id") or "").strip()
                if not ref_id:
                    continue
                if it.get("@type") in ("PartyRole", "PartyRoleRef"):
                    role_refs.append(ref_id)
                else:
                    party_refs.append(ref_id)
            if party_refs:
                partners = self.env["res.partner"].sudo().search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc012_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = self.env["tmf.party.role"].sudo().search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc012_party_role_ids"] = [(6, 0, roles.ids)]

            place_items = _loads(rec.tmfc012_place_ref_json) or []
            if isinstance(place_items, dict):
                place_items = [place_items]
            addr_refs, site_refs, loc_refs = [], [], []
            for it in place_items:
                if not isinstance(it, dict):
                    continue
                ref_id = str(it.get("id") or "").strip()
                if not ref_id:
                    continue
                rtype = str(it.get("@referredType") or it.get("@type") or "").lower()
                if "address" in rtype:
                    addr_refs.append(ref_id)
                elif "site" in rtype:
                    site_refs.append(ref_id)
                else:
                    loc_refs.append(ref_id)
            if addr_refs:
                addrs = self.env["tmf.geographic.address"].sudo().search([("tmf_id", "in", addr_refs)])
                if addrs:
                    updates["tmfc012_geographic_address_ids"] = [(6, 0, addrs.ids)]
            if site_refs:
                sites = self.env["tmf.geographic.site"].sudo().search([("tmf_id", "in", site_refs)])
                if sites:
                    updates["tmfc012_geographic_site_ids"] = [(6, 0, sites.ids)]
            if loc_refs:
                locs = self.env["tmf.geographic.location"].sudo().search([("tmf_id", "in", loc_refs)])
                if locs:
                    updates["tmfc012_geographic_location_ids"] = [(6, 0, locs.ids)]

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc012_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and any(
            k in vals for k in (
                "tmfc012_resource_spec_ref_json",
                "tmfc012_related_party_json",
                "tmfc012_place_ref_json",
            )
        ):
            try:
                self._tmfc012_resolve_refs()
            except Exception:
                pass
        return res
