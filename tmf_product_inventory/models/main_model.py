# -*- coding: utf-8 -*-
from odoo import models, fields, api

class TMFProduct(models.Model):
    _inherit = "tmf.product"

    # TMF637 típicos (si no existen ya en tmf_product)
    status = fields.Char()  # idealmente Selection si ya definiste catálogo de estados
    creation_date = fields.Datetime()
    order_date = fields.Datetime()
    start_date = fields.Datetime()
    termination_date = fields.Datetime()

    is_bundle = fields.Boolean(default=False)
    is_customer_visible = fields.Boolean(default=False)

    # Para avanzar rápido: almacenar subestructuras como JSON
    # (y más adelante normalizas a modelos hijos si quieres)
    product_characteristic_json = fields.Json(default=list)   # TMF: productCharacteristic[]
    related_party_json = fields.Json(default=list)            # TMF: relatedParty[]
    place_json = fields.Json(default=list)                    # TMF: place[]
    realizing_service_json = fields.Json(default=list)        # TMF: realizingService[]
    product_specification_json = fields.Json(default=dict)    # TMF: productSpecification (ref)

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ProductCreateEvent",
            "update": "ProductAttributeValueChangeEvent",
            "delete": "ProductDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("product", event_name, payload)
            except Exception:
                continue

    def to_tmf_json(self):
        self.ensure_one()
        tmf_id = self.tmf_id or str(self.id)
        return {
            "id": tmf_id,
            "href": f"/tmf-api/productInventoryManagement/v5/product/{tmf_id}",
            "@type": "Product",
            "name": self.name or "",
            "description": getattr(self, "description", "") or "",
            "isBundle": bool(self.is_bundle),
            "isCustomerVisible": bool(self.is_customer_visible),
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "orderDate": self.order_date.isoformat() if self.order_date else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "terminationDate": self.termination_date.isoformat() if self.termination_date else None,
            "status": self.status or None,
            "productCharacteristic": self.product_characteristic_json or [],
            "relatedParty": self.related_party_json or [],
            "place": self.place_json or [],
            "realizingService": self.realizing_service_json or [],
            "productSpecification": self.product_specification_json or None,
        }

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
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
