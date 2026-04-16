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


class TMFC039Agreement(models.Model):
    _inherit = "tmf.agreement"

    tmfc039_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc039_agreement_partner_rel",
        column1="agreement_id",
        column2="partner_id",
        string="TMFC039 Engaged Parties",
    )
    tmfc039_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc039_agreement_party_role_rel",
        column1="agreement_id",
        column2="party_role_id",
        string="TMFC039 Party Roles",
    )
    tmfc039_product_specification_ids = fields.Many2many(
        comodel_name="tmf.product.specification",
        relation="tmfc039_agreement_product_spec_rel",
        column1="agreement_id",
        column2="product_spec_id",
        string="TMFC039 Product Specifications",
    )

    def _tmfc039_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        PSpec = self.env["tmf.product.specification"].sudo()
        for rec in self:
            updates = {}
            engaged = _loads(rec.engaged_party) or []
            if isinstance(engaged, dict):
                engaged = [engaged]
            party_refs, role_refs = [], []
            for it in engaged:
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
                    updates["tmfc039_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc039_party_role_ids"] = [(6, 0, roles.ids)]

            items = _loads(rec.agreement_item) or []
            if isinstance(items, dict):
                items = [items]
            spec_refs = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                candidates = []
                po = it.get("productOffering")
                if isinstance(po, dict):
                    candidates.append(po)
                elif isinstance(po, list):
                    candidates.extend(po)
                ps = it.get("productSpecification")
                if isinstance(ps, dict):
                    candidates.append(ps)
                elif isinstance(ps, list):
                    candidates.extend(ps)
                prod = it.get("product")
                if isinstance(prod, dict):
                    ps2 = prod.get("productSpecification")
                    if isinstance(ps2, dict):
                        candidates.append(ps2)
                for ref in candidates:
                    if isinstance(ref, dict) and ref.get("id"):
                        spec_refs.append(str(ref["id"]))
            if spec_refs:
                specs = PSpec.search([("tmf_id", "in", spec_refs)])
                if specs:
                    updates["tmfc039_product_specification_ids"] = [(6, 0, specs.ids)]

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc039_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "engaged_party" in vals or "agreement_item" in vals
        ):
            try:
                self._tmfc039_resolve_refs()
            except Exception:
                pass
        return res
