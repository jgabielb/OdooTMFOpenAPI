from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    credit_blocked = fields.Boolean(
        string="Credit Blocked",
        default=False,
        copy=False,
        help="When true, new product orders for this partner are rejected with CREDIT_BLOCK_ACTIVE.",
    )
    credit_score = fields.Integer(
        string="Credit Score",
        copy=False,
        help="Last credit-rating-check score recorded by TMF645.",
    )
    credit_score_date = fields.Datetime(
        string="Credit Score Date",
        copy=False,
    )
