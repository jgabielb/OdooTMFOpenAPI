# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api

API_BASE = "/tmf-api/recommendationManagement/v4"


class TMFQueryProductRecommendation(models.Model):
    _name = "tmf.query.product.recommendation"
    _description = "TMF680 QueryProductRecommendation"
    _rec_name = "tmf_id"

    def _to_tmf_json(self, host):
        return {
            "id": self.tmf_id,
            "href": self.href or f"{host}{API_BASE}/queryProductRecommendation/{self.tmf_id}",
            "@type": self.tmf_type,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
            "state": self.state,
            "shoppingCart": self.shopping_cart,
            "shoppingCartItem": self.shopping_cart_item,
            "productOrder": self.product_order,
            "productOrderItem": self.product_order_item,
            "category": self.category,
            "relatedParty": self.related_party,
            "place": self.place,
            "recommendationItem": self.recommendation_item,
        }

    # TMF core identifiers
    tmf_id = fields.Char(
        string="ID",
        required=True,
        index=True,
        default=lambda self: str(uuid.uuid4())
    )

    href = fields.Char(index=True)

    tmf_type = fields.Char(
        string="@type",
        required=True,
        default="QueryProductRecommendation"
    )

    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    # Mandatory-at-least-one group (POST rule)
    shopping_cart = fields.Json()
    shopping_cart_item = fields.Json()
    product_order = fields.Json()
    product_order_item = fields.Json()
    category = fields.Json()
    related_party = fields.Json()
    place = fields.Json()

    # Output payload
    recommendation_item = fields.Json()

    # Metadata
    state = fields.Selection(
        [
            ("acknowledged", "acknowledged"),
            ("inProgress", "inProgress"),
            ("done", "done"),
            ("rejected", "rejected"),
        ],
        default="acknowledged",
        index=True,
    )

    create_date = fields.Datetime(readonly=True)

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "QueryProductRecommendationCreateEvent",
            "update": "QueryProductRecommendationAttributeValueChangeEvent",
            "delete": "QueryProductRecommendationDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            host = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            payloads = [rec._to_tmf_json(host=host) for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("queryProductRecommendation", event_name, payload)
            except Exception:
                continue

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        host = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        payloads = [rec._to_tmf_json(host=host) for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
