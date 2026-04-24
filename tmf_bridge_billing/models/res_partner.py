from odoo import fields, models


class ResPartnerBilling(models.Model):
    _inherit = "res.partner"

    tmf_customer_bill_ids = fields.One2many(
        "tmf.customer.bill", "partner_id",
        string="Customer Bills",
    )
