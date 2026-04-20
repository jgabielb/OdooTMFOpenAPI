from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Reverse lookups for the salesperson portfolio view
    tmf_account_ids = fields.One2many(
        "tmf.account", "partner_id",
        string="TMF Accounts",
    )
    tmf_account_count = fields.Integer(
        string="Accounts", compute="_compute_tmf_counts", store=False,
    )

    tmf_service_ids = fields.One2many(
        "tmf.service", "partner_id",
        string="TMF Services",
    )
    tmf_service_count = fields.Integer(
        string="Services", compute="_compute_tmf_counts", store=False,
    )

    tmf_order_ids = fields.One2many(
        "sale.order", "partner_id",
        string="Product Orders",
    )
    tmf_order_count = fields.Integer(
        string="Orders", compute="_compute_tmf_counts", store=False,
    )

    tmf_sales_lead_ids = fields.One2many(
        "tmf.sales.lead", "partner_id",
        string="Sales Leads",
    )
    tmf_sales_lead_count = fields.Integer(
        string="Leads", compute="_compute_tmf_counts", store=False,
    )

    def _compute_tmf_counts(self):
        for partner in self:
            partner.tmf_account_count = len(partner.tmf_account_ids)
            partner.tmf_service_count = len(partner.tmf_service_ids)
            partner.tmf_order_count = len(partner.tmf_order_ids)
            partner.tmf_sales_lead_count = len(partner.tmf_sales_lead_ids)
