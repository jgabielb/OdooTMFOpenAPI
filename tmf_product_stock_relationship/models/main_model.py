from odoo import api, fields, models


class TMFProductStock(models.Model):
    _name = "tmf.product.stock"
    _description = "TMF687 ProductStock"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char()
    description = fields.Char()
    product_stock_status_type = fields.Char(default="unknown")
    product_stock_level = fields.Json(default=dict)
    stocked_product = fields.Json(default=dict)
    extra_json = fields.Json(default=dict)
    product_id = fields.Many2one("product.product", string="Product", ondelete="set null")
    location_id = fields.Many2one("stock.location", string="Location", ondelete="set null")
    quantity = fields.Float(string="Quantity", default=0.0)
    reserved_quantity = fields.Float(string="Reserved Quantity", default=0.0)

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ProductStockCreateEvent",
            "update": "ProductStockAttributeValueChangeEvent",
            "delete": "ProductStockDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("productStock", event_name, payload)
            except Exception:
                continue

    def _get_tmf_api_path(self):
        return "/stock/v4/productStock"

    def _resolve_product_from_stocked_product(self):
        self.ensure_one()
        stocked = self.stocked_product or {}
        if not isinstance(stocked, dict):
            return self.env["product.product"]
        pid = stocked.get("id")
        if not pid:
            return self.env["product.product"]
        Product = self.env["product.product"].sudo()
        product = Product.search([("tmf_id", "=", str(pid))], limit=1)
        if not product and str(pid).isdigit():
            product = Product.browse(int(pid))
        return product if product and product.exists() else self.env["product.product"]

    def _sync_from_odoo_stock(self):
        Quant = self.env["stock.quant"].sudo()
        for rec in self:
            product = rec.product_id or rec._resolve_product_from_stocked_product()
            vals = {}
            if product and product.exists() and rec.product_id != product:
                vals["product_id"] = product.id

            quantity = rec.quantity
            reserved = rec.reserved_quantity

            if product and product.exists():
                domain = [("product_id", "=", product.id)]
                if rec.location_id:
                    domain.append(("location_id", "=", rec.location_id.id))
                else:
                    domain.append(("location_id.usage", "=", "internal"))
                quants = Quant.search(domain)
                if quants:
                    quantity = sum(quants.mapped("quantity"))
                    reserved = sum(quants.mapped("reserved_quantity"))
                else:
                    quantity = product.qty_available
                    free_qty = getattr(product, "free_qty", quantity)
                    reserved = max(0.0, quantity - free_qty)

            vals["quantity"] = quantity
            vals["reserved_quantity"] = reserved
            vals["product_stock_level"] = {
                "amount": quantity,
                "units": "unit",
                "reservedAmount": reserved,
            }
            if product and product.exists():
                vals["stocked_product"] = {
                    "id": str(product.tmf_id or product.id),
                    "name": product.display_name,
                    "@referredType": "Product",
                }
            super(TMFProductStock, rec.with_context(skip_tmf687_sync=True)).write(vals)

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ProductStock",
            "productStockLevel": self.product_stock_level or {},
            "productStockStatusType": self.product_stock_status_type or "unknown",
            "stockedProduct": self.stocked_product or {},
        }
        if self.name:
            payload["name"] = self.name
        if self.description:
            payload["description"] = self.description
        if isinstance(self.extra_json, dict):
            for k, v in self.extra_json.items():
                if k not in payload:
                    payload[k] = v
        if self.location_id:
            payload.setdefault("place", {
                "id": str(self.location_id.id),
                "name": self.location_id.display_name,
                "@referredType": "Location",
            })
        return payload

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_from_odoo_stock()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf687_sync"):
            self._sync_from_odoo_stock()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


class TMFReserveProductStock(models.Model):
    _name = "tmf.reserve.product.stock"
    _description = "TMF687 ReserveProductStock"
    _inherit = ["tmf.model.mixin"]

    reserve_product_stock_item = fields.Json(default=list)
    reserve_product_stock_state = fields.Char(default="accepted")
    extra_json = fields.Json(default=dict)

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ReserveProductStockCreateEvent",
            "update": "ReserveProductStockAttributeValueChangeEvent",
            "delete": "ReserveProductStockDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("reserveProductStock", event_name, payload)
            except Exception:
                continue

    def _get_tmf_api_path(self):
        return "/stock/v4/reserveProductStock"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ReserveProductStock",
            "reserveProductStockItem": self.reserve_product_stock_item or [],
            "reserveProductStockState": self.reserve_product_stock_state or "accepted",
        }
        if isinstance(self.extra_json, dict):
            for k, v in self.extra_json.items():
                if k not in payload:
                    payload[k] = v
        return payload

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec.reserve_product_stock_state = rec.reserve_product_stock_state or "accepted"
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
