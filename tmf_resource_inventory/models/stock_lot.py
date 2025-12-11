# tmf_resource_inventory/models/stock_lot.py

from odoo import api, fields, models


class StockLot(models.Model):
    _name = 'stock.lot' 
    _inherit = ['stock.lot', 'tmf.model.mixin']

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
            "serialNumber": self.name or self.ref,  # ajusta si tienes otro campo SN
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
            rec.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                api_name='resourceInventory',
                event_type='create',  # interno: create
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            # opcional: loggear en vez de silenciar
            # _logger.exception("Resource create event failed")
            pass
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                    api_name='resourceInventory',
                    event_type='update',  # interno: update
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                # _logger.exception("Resource update event failed")
                continue
        return res

    def unlink(self):
        # Guardamos el JSON antes de borrar
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                    api_name='resourceInventory',
                    event_type='delete',  # interno: delete
                    resource_json=resource,
                )
            except Exception:
                # _logger.exception("Resource delete event failed")
                continue
        return res
