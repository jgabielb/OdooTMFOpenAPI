from odoo import models, fields

class StockLot(models.Model):
    # In Odoo, 'stock.lot' represents a specific Serial Number
    _name = 'stock.lot' 
    _inherit = ['stock.lot', 'tmf.model.mixin']

    # TMF Resource Status
    resource_status = fields.Selection([
        ('standby', 'Standby'),
        ('alarm', 'Alarm'),
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('unknown', 'Unknown'),
        ('suspended', 'Suspended')
    ], default='available', string="Resource Status")

    def _get_tmf_api_path(self):
        return "/resourceInventory/v4/resource"