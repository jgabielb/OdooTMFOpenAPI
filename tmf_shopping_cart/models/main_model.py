from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.shopping.cart'
    _description = 'ShoppingCart'
    _inherit = ['tmf.model.mixin']

    cart_item = fields.Char(string="cartItem", help="")
    cart_total_price = fields.Char(string="cartTotalPrice", help="Total amount of the shopping cart, usually of money, that represents the actual price paid by the Cu")
    contact_medium = fields.Char(string="contactMedium", help="")
    related_party = fields.Char(string="relatedParty", help="")
    valid_for = fields.Char(string="validFor", help="The period for which the shopping cart is valid (e.g. 90 if no activity or 7 days if cart is empty)")

    def _get_tmf_api_path(self):
        return "/shopping_cartManagement/v4/ShoppingCart"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ShoppingCart",
            "cartItem": self.cart_item,
            "cartTotalPrice": self.cart_total_price,
            "contactMedium": self.contact_medium,
            "relatedParty": self.related_party,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('shoppingCart', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('shoppingCart', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='shoppingCart',
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
