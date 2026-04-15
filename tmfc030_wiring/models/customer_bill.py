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


class TMFC030CustomerBill(models.Model):
    _inherit = "tmf.customer.bill"

    tmfc030_billing_account_json = fields.Json(
        string="TMFC030 BillingAccount Ref (raw)",
        help="Raw TMF666 billingAccount fragment from TMF678 customerBill payload.",
    )
    tmfc030_billing_account_id = fields.Many2one(
        comodel_name="tmf.billing.account",
        string="TMFC030 Billing Account",
    )
    tmfc030_related_party_json = fields.Json(
        string="TMFC030 RelatedParty (raw)",
    )
    tmfc030_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc030_customer_bill_partner_rel",
        column1="customer_bill_id",
        column2="partner_id",
        string="TMFC030 Related Partners",
    )
    tmfc030_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc030_customer_bill_party_role_rel",
        column1="customer_bill_id",
        column2="party_role_id",
        string="TMFC030 Party Roles",
    )
    tmfc030_applied_rate_ids = fields.Many2many(
        comodel_name="tmf.applied.customer.billing.rate",
        relation="tmfc030_customer_bill_applied_rate_rel",
        column1="customer_bill_id",
        column2="applied_rate_id",
        string="TMFC030 Applied Billing Rates",
    )

    def _tmfc030_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Account = self.env["tmf.billing.account"].sudo()
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        Rate = self.env["tmf.applied.customer.billing.rate"].sudo()
        for rec in self:
            updates = {}

            acct = _loads(rec.tmfc030_billing_account_json) or {}
            if isinstance(acct, list):
                acct = acct[0] if acct else {}
            ref_id = str((acct or {}).get("id") or "").strip() if isinstance(acct, dict) else ""
            if ref_id:
                account = Account.search([("tmf_id", "=", ref_id)], limit=1)
                if account:
                    updates["tmfc030_billing_account_id"] = account.id

            items = _loads(rec.tmfc030_related_party_json) or []
            if items:
                party_refs, role_refs = [], []
                for it in items:
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
                        updates["tmfc030_related_partner_ids"] = [(6, 0, partners.ids)]
                if role_refs:
                    roles = PartyRole.search([("tmf_id", "in", role_refs)])
                    if roles:
                        updates["tmfc030_party_role_ids"] = [(6, 0, roles.ids)]

            if rec.tmf_id and "bill_id" in Rate._fields:
                rates = Rate.search([("bill_id", "=", rec.id)])
                if rates:
                    updates["tmfc030_applied_rate_ids"] = [(6, 0, rates.ids)]

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc030_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "tmfc030_billing_account_json" in vals
            or "tmfc030_related_party_json" in vals
        ):
            try:
                self._tmfc030_resolve_refs()
            except Exception:
                pass
        return res
