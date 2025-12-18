from odoo import models, fields, api

class ProductSpecification(models.Model):
    _name = 'tmf.product.specification'
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

    def to_tmf_json(self):
        """Return TMF620 ProductSpecification representation."""
        self.ensure_one()

        href = getattr(self, 'tmf_href', None)
        if not href:
            href = f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}"

        return {
            "id": self.tmf_id or str(self.id),
            "href": href,
            "name": self.name,
            "description": self.description or self.name,
            "@type": "ProductSpecification",
            "version": self.version,
            "lifecycleStatus": {
                'design': 'In Design',
                'active': 'Active',
                'retired': 'Retired',
            }.get(self.lifecycle_status, 'In Design'),
            "brand": self.brand,
            "productNumber": self.product_number,
        }
    
    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='productCatalog',
                event_type='ProductSpecificationCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productCatalog',
                    event_type='ProductSpecificationAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productCatalog',
                    event_type='ProductSpecificationDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res

    def action_set_active(self):
        self.lifecycle_status = 'active'

    def action_set_retired(self):
        self.lifecycle_status = 'retired'

    def action_reset_design(self):
        self.lifecycle_status = 'design'
    
    def _get_tmf_api_path(self):
        return "/productCatalogManagement/v4/productSpecification"