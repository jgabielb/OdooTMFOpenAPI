from odoo import api, fields, models
import json
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentTMF(models.Model):
    _inherit = "account.payment"

    tmf_payment_id = fields.Many2one(
        "tmf.payment", string="TMF Payment",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_payment(self):
        Payment = self.env["tmf.payment"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            total_amount = json.dumps({
                "unit": rec.currency_id.name or "USD",
                "value": rec.amount,
            })
            account_ref = json.dumps({
                "id": str(rec.partner_id.id) if rec.partner_id else "0",
                "name": rec.partner_id.name if rec.partner_id else "Unknown",
                "@referredType": "BillingAccount",
            })
            vals = {
                "name": rec.name or "Payment",
                "description": rec.ref or rec.name or "",
                "status": self._map_state_to_tmf(rec),
                "partner_id": rec.partner_id.id if rec.partner_id else False,
                "total_amount_json": total_amount,
                "account_json": account_ref,
                "payment_date": rec.date,
            }
            if rec.tmf_payment_id and rec.tmf_payment_id.exists():
                rec.tmf_payment_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            tmf_pay = Payment.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_payment_id": tmf_pay.id})
            if hasattr(tmf_pay, "account_payment_id"):
                tmf_pay.with_context(skip_tmf_bridge=True).write({"account_payment_id": rec.id})

    @staticmethod
    def _map_state_to_tmf(rec):
        state = getattr(rec, "state", "") or ""
        mapping = {
            "draft": "pendingAuthorization",
            "posted": "approved",
            "sent": "approved",
            "reconciled": "approved",
            "cancelled": "declined",
            "cancel": "declined",
        }
        return mapping.get(state, "pendingAuthorization")

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_payment()
            except Exception:
                _logger.warning("TMF bridge sync failed on account.payment create", exc_info=True)
        return recs

    def write(self, vals):
        res = super().write(vals)
        trigger = {"name", "ref", "partner_id", "amount", "state", "date"}
        if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
            try:
                self._sync_tmf_payment()
            except Exception:
                _logger.warning("TMF bridge sync failed on account.payment write", exc_info=True)
        return res
