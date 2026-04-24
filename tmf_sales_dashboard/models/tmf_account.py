from odoo import fields, models


class TMFAccountDashboard(models.Model):
    _inherit = "tmf.account"

    service_ids = fields.One2many(
        "tmf.service", "account_id",
        string="Services",
    )
    service_count = fields.Integer(
        string="Service Count", compute="_compute_service_count", store=False,
    )

    def _compute_service_count(self):
        for account in self:
            account.service_count = len(account.service_ids)
