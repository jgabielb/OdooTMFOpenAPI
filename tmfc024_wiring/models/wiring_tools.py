# -*- coding: utf-8 -*-
"""TMFC024 BillingAccountManagement wiring tools."""

from odoo import api, models


def _extract_id(payload):
    if not isinstance(payload, dict):
        return ""
    ev = payload.get("event")
    if isinstance(ev, dict) and isinstance(ev.get("resource"), dict):
        return str(ev["resource"].get("id") or "").strip()
    if isinstance(payload.get("resource"), dict):
        return str(payload["resource"].get("id") or "").strip()
    return str(payload.get("id") or "").strip()


class TMFC024WiringTools(models.AbstractModel):
    _name = "tmfc024.wiring.tools"
    _description = "TMFC024 Wiring Tools - Billing Account wiring"

    @api.model
    def _handle_party_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if not ref_id:
                return True
            accts = self.env["tmf.billing.account"].sudo().search(
                [("tmfc024_related_party_json", "ilike", ref_id)]
            )
            if accts:
                accts._tmfc024_resolve_refs()
        except Exception:
            pass
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_customer_bill_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if not ref_id:
                return True
            Bill = self.env["tmf.customer.bill"].sudo()
            bill = Bill.search([("tmf_id", "=", ref_id)], limit=1)
            if not bill or not bill.partner_id:
                return True
            accts = self.env["tmf.billing.account"].sudo().search(
                [("partner_id", "=", bill.partner_id.id)]
            )
            if accts:
                accts._tmfc024_resolve_refs()
        except Exception:
            pass
        return True

    @api.model
    def _handle_payment_method_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if not ref_id:
                return True
            method = self.env["tmf.payment.method"].sudo().search(
                [("tmf_id", "=", ref_id)], limit=1
            )
            if not method or not method.account_json:
                return True
            accts = self.env["tmf.billing.account"].sudo().search([])
            affected = accts.filtered(lambda a: a.tmf_id and a.tmf_id in (method.account_json or ""))
            if affected:
                affected._tmfc024_resolve_refs()
        except Exception:
            pass
        return True
