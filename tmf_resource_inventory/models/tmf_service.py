from odoo import models, fields

class TMFService(models.Model):
    _inherit = 'tmf.service'

    # Link Service -> Resource (One Service uses One Main Resource for now)
    resource_id = fields.Many2one(
        'stock.lot', 
        string="Supporting Resource",
        help="The physical device (SN) supporting this service"
    )