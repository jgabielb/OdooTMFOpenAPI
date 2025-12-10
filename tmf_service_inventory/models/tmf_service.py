from odoo import models, fields, api

class TMFService(models.Model):
    _name = 'tmf.service'
    _description = 'TMF Customer Service (Installed Base)'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Service Name", required=True)
    
    # Who owns this service?
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    
    # What kind of service is it?
    product_specification_id = fields.Many2one('product.specification', string="Specification")
    
    # Where did it come from?
    order_line_id = fields.Many2one('sale.order.line', string="Origin Order Line")
    
    start_date = fields.Datetime(string="Start Date", default=fields.Datetime.now)
    
    # TMF Lifecycle
    state = fields.Selection([
        ('feasibilityChecked', 'Feasibility Checked'),
        ('designed', 'Designed'),
        ('reserved', 'Reserved'),
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('terminated', 'Terminated')
    ], default='inactive', string="Status")

    def _get_tmf_api_path(self):
        return "/serviceInventory/v4/service"