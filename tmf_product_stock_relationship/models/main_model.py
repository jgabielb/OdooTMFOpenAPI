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

    def _get_tmf_api_path(self):
        return "/stock/v4/productStock"

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
        return payload


class TMFReserveProductStock(models.Model):
    _name = "tmf.reserve.product.stock"
    _description = "TMF687 ReserveProductStock"
    _inherit = ["tmf.model.mixin"]

    reserve_product_stock_item = fields.Json(default=list)
    reserve_product_stock_state = fields.Char(default="accepted")
    extra_json = fields.Json(default=dict)

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
        return recs
