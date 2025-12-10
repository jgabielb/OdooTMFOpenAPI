from odoo import models, fields, api

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'tmf.model.mixin']

    # TMF622 State Mapping
    # Odoo: draft -> TMF: Acknowledged
    # Odoo: sale -> TMF: InProgress
    # Odoo: done -> TMF: Completed
    # Odoo: cancel -> TMF: Cancelled
    
    tmf_status = fields.Selection([
        ('Acknowledged', 'Acknowledged'),
        ('InProgress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Rejected', 'Rejected')
    ], string="TMF Status", compute="_compute_tmf_status", store=True)

    description = fields.Text(string="Order Description")

    @api.depends('state')
    def _compute_tmf_status(self):
        for order in self:
            if order.state in ['draft', 'sent']:
                order.tmf_status = 'Acknowledged'
            elif order.state == 'sale':
                order.tmf_status = 'InProgress'
            elif order.state == 'done':
                order.tmf_status = 'Completed'
            elif order.state == 'cancel':
                order.tmf_status = 'Cancelled'
            else:
                order.tmf_status = 'Acknowledged'

    def _get_tmf_api_path(self):
        return "/productOrderingManagement/v4/productOrder"

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    # We inherit mixin here too because Lines have their own IDs in TMF
    _inherit = ['sale.order.line', 'tmf.model.mixin']

    def _get_tmf_api_path(self):
        # Lines usually don't have a direct top-level API, but they need UUIDs
        return ""