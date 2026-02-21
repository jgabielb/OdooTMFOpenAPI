from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.product.stock.relationship'
    _description = 'ProductStockRelationship'
    _inherit = ['tmf.model.mixin']

    relationship_type = fields.Char(string="relationshipType", help="The type of relationship between product stock")
    stock_level = fields.Char(string="stockLevel", help="A product stock  in relationship with this product stock")

    def _get_tmf_api_path(self):
        return "/product_stock_relationshipManagement/v4/ProductStockRelationship"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ProductStockRelationship",
            "relationshipType": self.relationship_type,
            "stockLevel": self.stock_level,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('productStockRelationship', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('productStockRelationship', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='productStockRelationship',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
