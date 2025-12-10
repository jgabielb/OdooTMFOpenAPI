from odoo import models, fields, api

class ProductSpecification(models.Model):
    _name = 'product.specification'
    _description = 'TMF Product Specification'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Specification Name", required=True)
    product_number = fields.Char(string="Product Number (SKU)", help="Technical SKU")
    brand = fields.Char(string="Brand")
    description = fields.Text(string="Description")
    
    version = fields.Char(string="Version", default="1.0")
    lifecycle_status = fields.Selection([
        ('design', 'In Design'),
        ('active', 'Active'),
        ('retired', 'Retired')
    ], default='design', string="Status")

    def action_set_active(self):
        self.lifecycle_status = 'active'

    def action_set_retired(self):
        self.lifecycle_status = 'retired'

    def action_reset_design(self):
        self.lifecycle_status = 'design'
    
    def _get_tmf_api_path(self):
        return "/productCatalogManagement/v4/productSpecification"