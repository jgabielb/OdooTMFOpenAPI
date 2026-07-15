# stock_lot.py (PATCH THIS FILE)

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

    # Optional: map these if you later add real fields
    administrative_state = fields.Selection([
        ('locked', 'Locked'),
        ('unlocked', 'Unlocked'),
        ('shutdown', 'Shutdown'),
    ], default='unlocked')

    operational_state = fields.Selection([
        ('enable', 'Enable'),
        ('disable', 'Disable'),
    ], default='enable')

    usage_state = fields.Selection([
        ('idle', 'Idle'),
        ('active', 'Active'),
        ('busy', 'Busy'),
    ], default='idle')
    warranty_end_date = fields.Date(string="Warranty End Date")
    current_location_id = fields.Many2one(
        "stock.location",
        string="Current Location",
        compute="_compute_inventory_links",
        store=False,
    )
    last_picking_id = fields.Many2one(
        "stock.picking",
        string="Last Picking",
        compute="_compute_inventory_links",
        store=False,
    )
    qty_available = fields.Float(
        string="Lot On Hand Quantity",
        compute="_compute_inventory_links",
        store=False,
    )

    def _get_tmf_api_path(self):
        return "/resourceInventoryManagement/v4/resource"

    def _compute_inventory_links(self):
        for rec in self:
            rec.current_location_id = False
            rec.last_picking_id = False
            rec.qty_available = 0.0

            quants = rec.quant_ids.filtered(lambda q: q.quantity)
            if quants:
                rec.current_location_id = quants[0].location_id
                rec.qty_available = sum(quants.mapped("quantity"))

            move_lines = rec.move_line_ids.sorted("id", reverse=True)
            if move_lines:
                rec.last_picking_id = move_lines[0].picking_id

    def to_tmf_json(self):
        self.ensure_one()

        tmf_id = getattr(self, 'tmf_id', None) or str(self.id)
        href = getattr(self, 'tmf_href', None) or (
            f"/tmf-api{self._get_tmf_api_path()}/{tmf_id}"
        )

        spec = None
        if self.product_id:
            # product.product may not carry tmf_id — fall back to numeric id
            prod_tmf_id = getattr(self.product_id, 'tmf_id', None) or str(self.product_id.id)
            spec = {
                "id": prod_tmf_id,
                "name": self.product_id.name,
                "href": f"/tmf-api/resourceCatalogManagement/v4/resourceSpecification/{prod_tmf_id}",
                "@referredType": "PhysicalResourceSpecification",
            }

        loc = getattr(self, 'current_location_id', None)

        return {
            "id": tmf_id,
            "href": href,
            "name": self.name or self.display_name,
            "@type": "Equipment",
            "@baseType": "Resource",
            "resourceStatus": getattr(self, 'resource_status', None) or "installed",
            "administrativeState": getattr(self, 'administrative_state', None) or "unlocked",
            "operationalState": getattr(self, 'operational_state', None) or "enable",
            "usageState": getattr(self, 'usage_state', None) or "idle",
            "serialNumber": self.name or getattr(self, 'ref', None),
            "warrantyEndDate": self.warranty_end_date.isoformat() if self.warranty_end_date else None,
            "resourceSpecification": spec,
            "place": [{
                "id": str(loc.id),
                "name": loc.display_name,
                "@referredType": "Location",
            }] if loc else None,
        }

    # ---------- Event hooks for /hub ----------
    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                api_name='resourceInventory',
                event_type='create',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                    api_name='resourceInventory',
                    event_type='update',
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
                self.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                    api_name='resourceInventory',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
