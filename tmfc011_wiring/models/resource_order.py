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


class TMFC011ResourceOrder(models.Model):
    _inherit = "tmf.resource.order"

    tmfc011_related_party_json = fields.Json(
        string="TMFC011 RelatedParty (raw)",
        help="Raw TMF632/TMF669 relatedParty fragment from TMF652 resourceOrder payload.",
    )
    tmfc011_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc011_resource_order_partner_rel",
        column1="resource_order_id",
        column2="partner_id",
        string="TMFC011 Related Partners",
    )
    tmfc011_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc011_resource_order_party_role_rel",
        column1="resource_order_id",
        column2="party_role_id",
        string="TMFC011 Party Roles",
    )
    tmfc011_resource_specification_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        relation="tmfc011_resource_order_resource_spec_rel",
        column1="resource_order_id",
        column2="resource_spec_id",
        string="TMFC011 Resource Specifications",
    )

    def _tmfc011_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        ResourceSpec = self.env["tmf.resource.specification"].sudo()
        for rec in self:
            updates = {}
            items = _loads(rec.tmfc011_related_party_json) or []
            if items:
                party_refs, role_refs = [], []
                for it in items:
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
                    partners = Partner.search([("tmf_id", "in", party_refs)])
                    if partners:
                        updates["tmfc011_related_partner_ids"] = [(6, 0, partners.ids)]
                if role_refs:
                    roles = PartyRole.search([("tmf_id", "in", role_refs)])
                    if roles:
                        updates["tmfc011_party_role_ids"] = [(6, 0, roles.ids)]

            spec_refs = []
            for item in rec.order_item_ids:
                res = item.resource_id
                if not res:
                    continue
                char = {c.name: c.value for c in res.characteristic_ids if c.name}
                ref_id = char.get("resourceSpecificationId") or res.tmf_resource_id
                if ref_id:
                    spec_refs.append(str(ref_id))
            if spec_refs:
                specs = ResourceSpec.search([("tmf_id", "in", spec_refs)])
                if specs:
                    updates["tmfc011_resource_specification_ids"] = [(6, 0, specs.ids)]

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc011_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "tmfc011_related_party_json" in vals or "order_item_ids" in vals
        ):
            try:
                self._tmfc011_resolve_refs()
            except Exception:
                pass
        return res
