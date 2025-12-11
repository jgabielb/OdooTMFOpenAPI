# tmf_resource_inventory/models/stock_lot.py (or similar)

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = ['stock.lot', 'tmf.model.mixin']

    # optional TMF-specific fields
    resource_status = fields.Selection([
        ('installed', 'Installed'),
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('retired', 'Retired'),
    ], string="Resource Status", default='installed')

    def _get_tmf_api_path(self):
        # base path for Resource Inventory
        return "/resourceInventory/v4/resource"

    def to_tmf_json(self):
        """Return TMF638 Resource representation."""
        self.ensure_one()

        href = getattr(self, 'tmf_href', None)
        if not href:
            href = f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}"

        return {
            "id": self.tmf_id or str(self.id),
            "href": href,
            "name": self.name or self.display_name,
            "@type": "Resource",
            "resourceStatus": self.resource_status or "installed",
            "serialNumber": self.name or self.ref,  # adjust to your SN field
            "resourceSpecification": {
                "id": self.product_id.tmf_id or str(self.product_id.id),
                "name": self.product_id.name,
                "@referredType": "ResourceSpecification",
            } if self.product_id else None,
        }

    # ---------- Event hooks for /hub (TMF638) ----------

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='resource',
                event_type='ResourceCreateEvent',
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
                    api_name='resource',
                    event_type='ResourceAttributeValueChangeEvent',
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
                    api_name='resource',
                    event_type='ResourceDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
