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

        href = getattr(self, 'tmf_href', None)
        if not href:
            href = f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}"

        spec = None
        if self.product_id:
            spec_id = self.product_id.tmf_id or str(self.product_id.id)
            spec = {
                "id": spec_id,
                "name": self.product_id.name,
                # Provide href as shown in examples :contentReference[oaicite:16]{index=16}
                "href": f"/tmf-api/resourceCatalogManagement/v4/resourceSpecification/{spec_id}",
                "@referredType": "PhysicalResourceSpecification",
            }

        return {
            "id": self.tmf_id or str(self.id),
            "href": href,
            "name": self.name or self.display_name,

            # Polymorphism/extension meta-attributes :contentReference[oaicite:17]{index=17}
            "@type": "Equipment",
            "@baseType": "Resource",

            "resourceStatus": self.resource_status or "installed",
            "administrativeState": self.administrative_state or "unlocked",
            "operationalState": self.operational_state or "enable",
            "usageState": self.usage_state or "idle",

            "serialNumber": self.name or self.ref,
            "resourceSpecification": spec,
            "place": [{
                "id": str(self.current_location_id.id),
                "name": self.current_location_id.display_name,
                "@referredType": "Location",
            }] if self.current_location_id else None,
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
