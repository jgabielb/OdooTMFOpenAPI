from odoo import api, models, fields


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'tmf.model.mixin']

    # Link Commercial Offering -> Technical Spec
    product_specification_id = fields.Many2one(
        'tmf.product.specification',
        string="Technical Specification",
        help="The technical definition behind this commercial offering"
    )

    # Bundle: this offering wraps child offerings
    bundled_offering_ids = fields.Many2many(
        'product.template',
        'product_template_bundle_rel',
        'bundle_id',
        'component_id',
        string="Bundled Component Offerings",
    )

    lifecycle_status = fields.Selection([
        ('design', 'In Design'),
        ('active', 'Active'),
        ('retired', 'Retired')
    ], default='active', string="TMF Status")

    def _get_tmf_api_path(self):
        # used by tmf.model.mixin to build href
        return "/productCatalogManagement/v5/productOffering"

    # ------------- TMF620 JSON SERIALIZER -------------

    def to_tmf_json(self):
        """Return TMF620 ProductOffering representation."""
        self.ensure_one()

        # if your mixin exposes href, use that; otherwise build it
        href = getattr(self, 'tmf_href', None)
        if not href:
            # fallback: relative href
            href = f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}"

        return {
            "id": self.tmf_id or str(self.id),
            "href": href,
            "name": self.name,
            "description": self.description or self.name,
            "@type": "ProductOffering",
            # minimal TMF fields – you can add more later
            "lifecycleStatus": self.lifecycle_status.capitalize() if self.lifecycle_status else None,
            "isBundle": bool(self.bundled_offering_ids),
            "productSpecification": (
                {
                    "id": self.product_specification_id.tmf_id
                           or str(self.product_specification_id.id),
                    "name": self.product_specification_id.name,
                    "@referredType": "ProductSpecification",
                } if self.product_specification_id else None
            ),
            "bundledProductOffering": [
                {
                    "id": c.tmf_id or str(c.id),
                    "name": c.name,
                    "@type": "BundledProductOffering",
                }
                for c in self.bundled_offering_ids
            ] if self.bundled_offering_ids else [],
        }

    # ------------- EVENT HOOKS FOR /hub (TMF620) -------------

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='productOffering',
                event_type='ProductOfferingCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            # never break normal create if notification fails
            pass
        return rec

    def write(self, vals):
        state_changed = "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOffering',
                    event_type='ProductOfferingAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
                if state_changed:
                    rec.env['tmf.hub.subscription']._notify_subscribers(
                        api_name='productOffering',
                        event_type='ProductOfferingStateChangeEvent',
                        resource_json=rec.to_tmf_json(),
                    )
            except Exception:
                continue
        return res

    def unlink(self):
        # keep payload before deletion
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productOffering',
                    event_type='ProductOfferingDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
