from odoo import fields, models


class TMFAccountBilling(models.Model):
    """Add billing relationship fields to TMF Account."""
    _inherit = "tmf.account"

    billing_account_id = fields.Many2one(
        "tmf.account",
        string="Billing Account",
        domain="[('resource_type', '=', 'BillingAccount'), ('partner_id', '=', partner_id)]",
        ondelete="set null",
        help="The BillingAccount associated with this PartyAccount",
    )
    party_account_id = fields.Many2one(
        "tmf.account",
        string="Party Account",
        domain="[('resource_type', '=', 'PartyAccount'), ('partner_id', '=', partner_id)]",
        ondelete="set null",
        help="The PartyAccount this BillingAccount belongs to",
    )
