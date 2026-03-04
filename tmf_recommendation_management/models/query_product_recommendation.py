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
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

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

    def _resolve_partner(self):
        self.ensure_one()
        refs = self.related_party
        if isinstance(refs, dict):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        env_partner = self.env["res.partner"].sudo()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (ref.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _resolve_sale_order(self):
        self.ensure_one()
        env_so = self.env["sale.order"].sudo()
        refs = []
        if isinstance(self.shopping_cart, dict):
            refs.append(self.shopping_cart)
        if isinstance(self.product_order, dict):
            refs.append(self.product_order)
        for ref in refs:
            rid = ref.get("id")
            if not rid:
                continue
            so = env_so.search([("client_order_ref", "=", str(rid))], limit=1)
            if so:
                return so
        if self.partner_id:
            so = env_so.search([("partner_id", "=", self.partner_id.id), ("state", "=", "draft")], limit=1)
            if so:
                return so
        return False

    def _resolve_product_template(self):
        self.ensure_one()
        env_pt = self.env["product.template"].sudo()
        items = self.recommendation_item
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            product = item.get("product") or {}
            if not isinstance(product, dict):
                continue
            rid = product.get("id")
            if rid:
                pt = env_pt.search([("tmf_id", "=", str(rid))], limit=1)
                if pt:
                    return pt
            name = (product.get("name") or "").strip()
            if name:
                pt = env_pt.search([("name", "=", name)], limit=1)
                if pt:
                    return pt
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            so = rec._resolve_sale_order()
            if so:
                rec.sale_order_id = so.id
            pt = rec._resolve_product_template()
            if pt:
                rec.product_tmpl_id = pt.id

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
        recs._sync_native_links()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if (
            "related_party" in vals
            or "shopping_cart" in vals
            or "product_order" in vals
            or "recommendation_item" in vals
            or "partner_id" in vals
            or "sale_order_id" in vals
            or "product_tmpl_id" in vals
        ):
            self._sync_native_links()
        self._notify("update")
        return res

    def unlink(self):
        host = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        payloads = [rec._to_tmf_json(host=host) for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
