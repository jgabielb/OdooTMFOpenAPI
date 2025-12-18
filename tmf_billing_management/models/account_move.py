from odoo import models, fields, api

class AccountMove(models.Model):
    _name = 'account.move' # Standard Odoo Invoice
    _inherit = ['account.move', 'tmf.model.mixin']

    # Link to the specific Billing Account we just created
    billing_account_id = fields.Many2one('tmf.billing.account', string="Billing Account")

    def _get_tmf_api_path(self):
        return "/customerBillManagement/v4/customerBill"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id or str(self.id),
            "href": self.href,
            "billNo": self.name,
            "billDate": self.invoice_date.isoformat() if self.invoice_date else None,
            "paymentDueDate": self.invoice_date_due.isoformat() if self.invoice_date_due else None,
            "state": "settled" if self.payment_state == 'paid' else "due",
            "amountDue": {"value": self.amount_residual, "unit": self.currency_id.name},
            "billDocument": [{
                "id": str(self.id),
                "name": f"Invoice_{self.name}.pdf",
                "url": f"/web/content/account.move/{self.id}/action_invoice_sent" # Simplified URL
            }]
        }