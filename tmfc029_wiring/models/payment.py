# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


def _loads(value):
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


class TMFC029PaymentWiring(models.Model):
    """TMFC029 side-car fields on tmf.payment.

    Resolves TMF666 BillingAccount, TMF678 CustomerBill and TMF632 Party
    references found inside the payment payload into Odoo records, so
    PaymentManagement participates in ODA cross-component navigation.

    Never alters CTK-facing TMF676 fields or events.
    """

    _inherit = "tmf.payment"

    tmfc029_billing_account_id = fields.Many2one(
        "tmf.billing.account",
        string="Billing Account (TMF666)",
        ondelete="set null",
        help="Resolved TMF666 BillingAccount referenced from account_json.",
    )

    tmfc029_customer_bill_ids = fields.Many2many(
        "tmf.customer.bill",
        "tmfc029_payment_customer_bill_rel",
        "payment_id",
        "bill_id",
        string="Customer Bills (TMF678)",
        help="Resolved TMF678 CustomerBill records from paymentItem.item refs.",
    )

    tmfc029_related_partner_ids = fields.Many2many(
        "res.partner",
        "tmfc029_payment_partner_rel",
        "payment_id",
        "partner_id",
        string="Related Partners (TMF632)",
        help="Resolved TMF632 Party references from account_json/related parties.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        try:
            recs._tmfc029_resolve_refs()
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC029: resolve on create failed: %s", exc)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ("account_json", "payment_item_json", "partner_id")):
            try:
                self._tmfc029_resolve_refs()
            except Exception as exc:  # pragma: no cover - defensive
                _logger.exception("TMFC029: resolve on write failed: %s", exc)
        return res

    def _tmfc029_resolve_refs(self):
        BillingAccount = self.env["tmf.billing.account"].sudo()
        CustomerBill = self.env["tmf.customer.bill"].sudo()
        Partner = self.env["res.partner"].sudo()
        ctx = {"skip_tmf_wiring": True}

        for rec in self:
            updates = {}

            account = _loads(rec.account_json) or {}
            account_id = str((account or {}).get("id") or "").strip()
            if account_id:
                ba = BillingAccount.search([("tmf_id", "=", account_id)], limit=1)
                if not ba and account_id.isdigit():
                    ba = BillingAccount.browse(int(account_id))
                    if not ba.exists():
                        ba = BillingAccount.browse([])
                if ba and (not rec.tmfc029_billing_account_id or rec.tmfc029_billing_account_id.id != ba.id):
                    updates["tmfc029_billing_account_id"] = ba.id

            items = _loads(rec.payment_item_json) or []
            if isinstance(items, dict):
                items = [items]
            bill_ids = []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                ref = (item.get("item") or {}) if isinstance(item.get("item"), dict) else {}
                bid = str(ref.get("id") or "").strip()
                if not bid:
                    continue
                bill = CustomerBill.search([("tmf_id", "=", bid)], limit=1)
                if not bill and bid.isdigit():
                    bill = CustomerBill.browse(int(bid))
                    if not bill.exists():
                        bill = CustomerBill.browse([])
                if bill:
                    bill_ids.append(bill.id)
            if bill_ids:
                updates["tmfc029_customer_bill_ids"] = [(6, 0, bill_ids)]

            partner_ids = []
            if rec.partner_id:
                partner_ids.append(rec.partner_id.id)
            related = (account or {}).get("relatedParty") or []
            if isinstance(related, dict):
                related = [related]
            for ref in related if isinstance(related, list) else []:
                if not isinstance(ref, dict):
                    continue
                pid = str(ref.get("id") or "").strip()
                if not pid:
                    continue
                p = Partner.search([("tmf_id", "=", pid)], limit=1)
                if not p and pid.isdigit():
                    p = Partner.browse(int(pid))
                    if not p.exists():
                        p = Partner.browse([])
                if p:
                    partner_ids.append(p.id)
            if partner_ids:
                updates["tmfc029_related_partner_ids"] = [(6, 0, list(set(partner_ids)))]

            if updates:
                rec.with_context(**ctx).write(updates)
