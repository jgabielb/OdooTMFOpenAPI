from odoo import models, fields

class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'tmf.model.mixin']

    # Link Commercial Offering -> Technical Spec
    product_specification_id = fields.Many2one(
        'product.specification', 
        string="Technical Specification",
        help="The technical definition behind this commercial offering"
    )

    lifecycle_status = fields.Selection([
        ('design', 'In Design'),
        ('active', 'Active'),
        ('retired', 'Retired')
    ], default='active', string="TMF Status")

    def _get_tmf_api_path(self):
        return "/productCatalogManagement/v4/productOffering"