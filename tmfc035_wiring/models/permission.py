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


def _extract_ref_ids(node):
    """Accept dict or list, return (party_ids, party_role_ids)."""
    party, roles = [], []
    items = node if isinstance(node, list) else [node] if isinstance(node, dict) else []
    for it in items:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("id") or "").strip()
        if not rid:
            continue
        if it.get("@type") in ("PartyRole", "PartyRoleRef"):
            roles.append(rid)
        else:
            party.append(rid)
    return party, roles


class TMFC035Permission(models.Model):
    _inherit = "tmf672.permission"

    tmfc035_user_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc035_perm_user_partner_rel",
        column1="perm_id",
        column2="partner_id",
        string="TMFC035 User Partners",
    )
    tmfc035_granter_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc035_perm_granter_partner_rel",
        column1="perm_id",
        column2="partner_id",
        string="TMFC035 Granter Partners",
    )
    tmfc035_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc035_perm_party_role_rel",
        column1="perm_id",
        column2="party_role_id",
        string="TMFC035 Party Roles",
    )

    def _tmfc035_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        for rec in self:
            updates = {}
            user_party, user_roles = _extract_ref_ids(_loads(rec.user_json))
            granter_party, granter_roles = _extract_ref_ids(_loads(rec.granter_json))

            if user_party:
                partners = Partner.search([("tmf_id", "in", user_party)])
                if partners:
                    updates["tmfc035_user_partner_ids"] = [(6, 0, partners.ids)]
            if granter_party:
                partners = Partner.search([("tmf_id", "in", granter_party)])
                if partners:
                    updates["tmfc035_granter_partner_ids"] = [(6, 0, partners.ids)]
            all_roles = list({*user_roles, *granter_roles})
            if all_roles:
                roles = PartyRole.search([("tmf_id", "in", all_roles)])
                if roles:
                    updates["tmfc035_party_role_ids"] = [(6, 0, roles.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc035_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "user_json" in vals or "granter_json" in vals
        ):
            try:
                self._tmfc035_resolve_refs()
            except Exception:
                pass
        return res


class TMFC035UserRole(models.Model):
    _inherit = "tmf672.user.role"

    tmfc035_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc035_user_role_party_role_rel",
        column1="user_role_id",
        column2="party_role_id",
        string="TMFC035 Party Roles",
    )

    def _tmfc035_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        PartyRole = self.env["tmf.party.role"].sudo()
        for rec in self:
            role_name = (rec.involvement_role or "").strip()
            if not role_name:
                continue
            roles = PartyRole.search([("name", "=", role_name)])
            if roles:
                rec.with_context(**ctx).write({
                    "tmfc035_party_role_ids": [(6, 0, roles.ids)],
                })
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc035_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and "involvement_role" in vals:
            try:
                self._tmfc035_resolve_refs()
            except Exception:
                pass
        return res
