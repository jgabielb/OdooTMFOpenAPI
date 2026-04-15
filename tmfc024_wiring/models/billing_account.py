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


class TMFC024BillingAccount(models.Model):
    _inherit = "tmf.billing.account"

    tmfc024_related_party_json = fields.Json(
        string="TMFC024 RelatedParty (raw)",
        help="Raw TMF632/TMF669 relatedParty fragment from TMF666 billingAccount payload.",
    )
    tmfc024_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc024_billing_account_partner_rel",
        column1="billing_account_id",
        column2="partner_id",
        string="TMFC024 Related Partners",
    )
    tmfc024_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc024_billing_account_party_role_rel",
        column1="billing_account_id",
        column2="party_role_id",
        string="TMFC024 Party Roles",
    )
    tmfc024_customer_bill_ids = fields.Many2many(
        comodel_name="tmf.customer.bill",
        relation="tmfc024_billing_account_customer_bill_rel",
        column1="billing_account_id",
        column2="customer_bill_id",
        string="TMFC024 Customer Bills",
    )
    tmfc024_payment_method_ids = fields.Many2many(
        comodel_name="tmf.payment.method",
        relation="tmfc024_billing_account_payment_method_rel",
        column1="billing_account_id",
        column2="payment_method_id",
        string="TMFC024 Payment Methods",
    )

    def _tmfc024_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        Bill = self.env["tmf.customer.bill"].sudo()
        PayMethod = self.env["tmf.payment.method"].sudo()
        for rec in self:
            updates = {}
            items = _loads(rec.tmfc024_related_party_json) or []
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
                        updates["tmfc024_related_partner_ids"] = [(6, 0, partners.ids)]
                if role_refs:
                    roles = PartyRole.search([("tmf_id", "in", role_refs)])
                    if roles:
                        updates["tmfc024_party_role_ids"] = [(6, 0, roles.ids)]
            # Link bills for the same account holder
            if rec.partner_id:
                bills = Bill.search([("partner_id", "=", rec.partner_id.id)])
                if bills:
                    updates["tmfc024_customer_bill_ids"] = [(6, 0, bills.ids)]
            # Payment methods referencing this account via account_json
            if rec.tmf_id:
                methods = PayMethod.search([("account_json", "ilike", rec.tmf_id)])
                if methods:
                    updates["tmfc024_payment_method_ids"] = [(6, 0, methods.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc024_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "tmfc024_related_party_json" in vals or "partner_id" in vals
        ):
            try:
                self._tmfc024_resolve_refs()
            except Exception:
                pass
        return res
