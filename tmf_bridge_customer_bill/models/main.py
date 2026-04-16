from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class AccountMoveTMFBill(models.Model):
    _inherit = "account.move"

    tmf_customer_bill_id = fields.Many2one(
        "tmf.customer.bill", string="TMF Customer Bill",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_customer_bill(self):
        Bill = self.env["tmf.customer.bill"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            if rec.move_type != "out_invoice":
                continue
            vals = {
                "name": rec.name or "Invoice",
                "state": "validated" if rec.state == "posted" else "new",
                "partner_id": rec.partner_id.id if rec.partner_id else False,
            }
            if hasattr(rec, "tmf_customer_bill_id") and rec.tmf_customer_bill_id and rec.tmf_customer_bill_id.exists():
                rec.tmf_customer_bill_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            bill = Bill.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_customer_bill_id": bill.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_customer_bill()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_bridge") and "state" in vals:
            try:
                self._sync_tmf_customer_bill()
            except Exception:
                _logger.warning("TMF bridge sync failed", exc_info=True)
        return res
