# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TMFC040Usage(models.Model):
    _inherit = "tmf.usage"

    tmfc040_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc040_usage_partner_rel",
        column1="usage_id",
        column2="partner_id",
        string="TMFC040 Engaged Parties",
    )
    tmfc040_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc040_usage_party_role_rel",
        column1="usage_id",
        column2="party_role_id",
        string="TMFC040 Party Roles",
    )
    tmfc040_billing_account_ids = fields.Many2many(
        comodel_name="tmf.billing.account",
        relation="tmfc040_usage_billing_account_rel",
        column1="usage_id",
        column2="billing_account_id",
        string="TMFC040 Billing Accounts",
    )

    def _tmfc040_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        BA = self.env["tmf.billing.account"].sudo()
        for rec in self:
            party_refs, role_refs, ba_refs = [], [], []
            for rp in rec.related_party_ids:
                rid = (rp.party_id or "").strip()
                if not rid:
                    continue
                rt = (rp.referred_type or "").lower()
                if "billingaccount" in rt:
                    ba_refs.append(rid)
                elif "partyrole" in rt or (rp.role or ""):
                    role_refs.append(rid)
                    party_refs.append(rid)
                else:
                    party_refs.append(rid)
            updates = {}
            if party_refs:
                partners = Partner.search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc040_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc040_party_role_ids"] = [(6, 0, roles.ids)]
            if ba_refs:
                bas = BA.search([("tmf_id", "in", ba_refs)])
                if bas:
                    updates["tmfc040_billing_account_ids"] = [(6, 0, bas.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc040_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                self._tmfc040_resolve_refs()
            except Exception:
                pass
        return res
