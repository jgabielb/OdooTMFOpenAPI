from odoo import fields, models


class TMFAccountBilling(models.Model):
    """Add billing relationship fields to TMF Account."""
    _inherit = "tmf.account"

    billing_account_id = fields.Many2one(
        "tmf.account",
        string="Billing Account",
        ondelete="set null",
        help="The BillingAccount associated with this PartyAccount",
    )
    party_account_id = fields.Many2one(
        "tmf.account",
        string="Party Account",
        ondelete="set null",
        help="The PartyAccount this BillingAccount belongs to",
    )
