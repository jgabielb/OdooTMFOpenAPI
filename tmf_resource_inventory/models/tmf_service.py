from odoo import fields, models


class TMFService(models.Model):
    _inherit = "tmf.service"

    # Keep TMF638 serialization in tmf_service_inventory and only extend with stock links here.
    resource_id = fields.Many2one(
        "stock.lot",
        string="Supporting Resource",
        help="Physical/virtual resource supporting this service",
    )
