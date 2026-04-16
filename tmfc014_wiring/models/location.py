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


def _collect_party_refs(items):
    party_refs, role_refs = [], []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("id") or "").strip()
        if not rid:
            continue
        if it.get("@type") in ("PartyRole", "PartyRoleRef"):
            role_refs.append(rid)
        else:
            party_refs.append(rid)
    return party_refs, role_refs


class TMFC014GeographicAddress(models.Model):
    _inherit = "tmf.geographic.address"

    tmfc014_related_party_json = fields.Json(string="TMFC014 RelatedParty (raw)")
    tmfc014_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc014_ga_partner_rel",
        column1="ga_id",
        column2="partner_id",
        string="TMFC014 Related Partners",
    )
    tmfc014_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc014_ga_party_role_rel",
        column1="ga_id",
        column2="party_role_id",
        string="TMFC014 Party Roles",
    )

    def _tmfc014_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        for rec in self:
            items = _loads(rec.tmfc014_related_party_json) or []
            party_refs, role_refs = _collect_party_refs(items)
            updates = {}
            if party_refs:
                partners = Partner.search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc014_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc014_party_role_ids"] = [(6, 0, roles.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc014_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and "tmfc014_related_party_json" in vals:
            try:
                self._tmfc014_resolve_refs()
            except Exception:
                pass
        return res


class TMFC014GeographicSite(models.Model):
    _inherit = "tmf.geographic.site"

    tmfc014_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc014_gs_partner_rel",
        column1="gs_id",
        column2="partner_id",
        string="TMFC014 Related Partners",
    )
    tmfc014_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc014_gs_party_role_rel",
        column1="gs_id",
        column2="party_role_id",
        string="TMFC014 Party Roles",
    )

    def _tmfc014_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        for rec in self:
            items = _loads(rec.related_party_json) or []
            party_refs, role_refs = _collect_party_refs(items)
            updates = {}
            if party_refs:
                partners = Partner.search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc014_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc014_party_role_ids"] = [(6, 0, roles.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc014_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and "related_party_json" in vals:
            try:
                self._tmfc014_resolve_refs()
            except Exception:
                pass
        return res
