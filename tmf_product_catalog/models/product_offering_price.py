from odoo import models, fields, api


class ProductOfferingPrice(models.Model):
    _name = 'tmf.product.offering.price'
    _description = 'TMF Product Offering Price'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Price Name", required=True)
    description = fields.Text(string="Description")
    version = fields.Char(string="Version", default="1.0")
    lifecycle_status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('retired', 'Retired'),
    ], default='active', string="Status")

    price_type = fields.Char(string="Price Type")
    unit_of_measure = fields.Char(string="Unit of Measure")

    # Monetary price stored as JSON (TMF PricingLogicAlgorithm / Price)
    price_json = fields.Text(string="Price (JSON)")

    offering_id = fields.Many2one(
        'product.template',
        string="Product Offering",
        ondelete='set null',
    )

    def _get_tmf_api_path(self):
        return "/productCatalogManagement/v5/productOfferingPrice"

    def to_tmf_json(self):
        self.ensure_one()
        import json
        price = {}
        if self.price_json:
            try:
                price = json.loads(self.price_json)
            except Exception:
                pass
        result = {
            "id": self.tmf_id or str(self.id),
            "href": f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}",
            "name": self.name,
            "description": self.description or "",
            "version": self.version or "1.0",
            "lifecycleStatus": self.lifecycle_status or "active",
            "@type": "ProductOfferingPrice",
        }
        if self.price_type:
            result["priceType"] = self.price_type
        if price:
            result["price"] = price
        return result

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='productOfferingPrice',
                event_type='ProductOfferingPriceCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec

    def write(self, vals):
        state_changed = "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOfferingPrice',
                    event_type='ProductOfferingPriceAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
                if state_changed:
                    rec.env['tmf.hub.subscription']._notify_subscribers(
                        api_name='productOfferingPrice',
                        event_type='ProductOfferingPriceStateChangeEvent',
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
                    api_name='productOfferingPrice',
                    event_type='ProductOfferingPriceDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
