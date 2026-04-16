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


class TMFC009ServiceQualification(models.Model):
    _inherit = "tmf.service.qualification"

    tmfc009_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc009_sq_partner_rel",
        column1="sq_id",
        column2="partner_id",
        string="TMFC009 Related Partners",
    )
    tmfc009_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc009_sq_party_role_rel",
        column1="sq_id",
        column2="party_role_id",
        string="TMFC009 Party Roles",
    )
    tmfc009_service_specification_ids = fields.Many2many(
        comodel_name="tmf.service.specification",
        relation="tmfc009_sq_service_spec_rel",
        column1="sq_id",
        column2="service_spec_id",
        string="TMFC009 Service Specifications",
    )

    def _tmfc009_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        ServiceSpec = self.env["tmf.service.specification"].sudo()
        for rec in self:
            updates = {}
            parties = _loads(rec.related_party_json) or []
            party_refs, role_refs = [], []
            for it in parties:
                if not isinstance(it, dict):
                    continue
                rid = str(it.get("id") or "").strip()
                if not rid:
                    continue
                if it.get("@type") in ("PartyRole", "PartyRoleRef"):
                    role_refs.append(rid)
                else:
                    party_refs.append(rid)
            if party_refs:
                partners = Partner.search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc009_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc009_party_role_ids"] = [(6, 0, roles.ids)]

            spec_refs = []
            items = _loads(rec.service_qualification_item_json) or []
            for it in items:
                if not isinstance(it, dict):
                    continue
                svc = it.get("service") or {}
                spec = svc.get("serviceSpecification") if isinstance(svc, dict) else None
                if isinstance(spec, dict):
                    sid = str(spec.get("id") or "").strip()
                    if sid:
                        spec_refs.append(sid)
            if spec_refs:
                specs = ServiceSpec.search([("tmf_id", "in", spec_refs)])
                if specs:
                    updates["tmfc009_service_specification_ids"] = [(6, 0, specs.ids)]

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc009_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "related_party_json" in vals or "service_qualification_item_json" in vals
        ):
            try:
                self._tmfc009_resolve_refs()
            except Exception:
                pass
        return res
