# -*- coding: utf-8 -*-
import uuid
import json
from odoo import models, fields, api

from .common import _as_dict, _as_list, _filter_top_level_fields

API_BASE = "/tmf-api/resourcePoolManagement/v5/resourcePool"


class TMFResourcePool(models.Model):
    _name = "tmf.resource.pool"
    _description = "TMF685 ResourcePool"
    _rec_name = "name"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)

    tmf_type = fields.Char(required=True, default="ResourcePool")  # @type

    name = fields.Char(required=True)
    description = fields.Text()

    # Mandatory (as per conformance profile) :contentReference[oaicite:2]{index=2}
    capacity = fields.Text(required=True, help="JSON: capacity")
    pooled_resource = fields.Text(required=True, help="JSON list: pooledResource[]")
    pooled_resource_specification = fields.Text(required=True, help="JSON list: pooledResourceSpecification[]")

    # Optional (store as JSON)
    activation_feature = fields.Text(help="JSON list: activationFeature[]")
    related_party = fields.Text(help="JSON list: relatedParty[]")
    place = fields.Text(help="JSON list: place[]")
    resource_characteristic = fields.Text(help="JSON list: resourceCharacteristic[]")
    resource_relationship = fields.Text(help="JSON list: resourceRelationship[]")
    supporting_resource = fields.Text(help="JSON list: supportingResource[]")
    resource_specification = fields.Text(help="JSON: resourceSpecification")

    # Simple state fields (optional, CTK may assert presence if you include them)
    administrative_state = fields.Char()
    operational_state = fields.Char()
    usage_state = fields.Char()
    resource_status = fields.Char()
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    stock_location_id = fields.Many2one("stock.location", string="Stock Location", ondelete="set null")

    def _resolve_partner(self):
        self.ensure_one()
        refs = _as_list(self.related_party)
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

    def _resolve_stock_location(self):
        self.ensure_one()
        env_loc = self.env["stock.location"].sudo()
        if self.name:
            loc = env_loc.search([("name", "=", self.name)], limit=1)
            if loc:
                return loc
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            loc = rec._resolve_stock_location()
            if loc:
                rec.stock_location_id = loc.id

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ResourcePoolCreateEvent",
            "update": "ResourcePoolAttributeValueChangeEvent",
            "delete": "ResourcePoolDeleteEvent",
        }
        if payloads is None:
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            payloads = [rec.to_tmf_json(host_url=base_url) for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("resourcePool", event_name, payload)
            except Exception:
                continue

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")
        base_url = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        href_value = self.href or f"{host_url}{API_BASE}/{self.tmf_id}"
        if isinstance(href_value, str) and href_value.startswith("/"):
            href_value = f"{base_url}{href_value}" if base_url else href_value
        payload = {
            "id": str(self.tmf_id),
            "href": href_value,
            "@type": self.tmf_type,

            "name": self.name,
            "description": self.description,

            "capacity": _as_dict(self.capacity) or {},
            "pooledResource": _as_list(self.pooled_resource) or [],
            "pooledResourceSpecification": _as_list(self.pooled_resource_specification) or [],

            "activationFeature": _as_list(self.activation_feature) or None,
            "relatedParty": _as_list(self.related_party) or None,
            "place": _as_list(self.place) or None,
            "resourceCharacteristic": _as_list(self.resource_characteristic) or None,
            "resourceRelationship": _as_list(self.resource_relationship) or None,
            "supportingResource": _as_list(self.supporting_resource) or None,
            "resourceSpecification": json.loads(self.resource_specification) if self.resource_specification else None,

            "administrativeState": self.administrative_state,
            "operationalState": self.operational_state,
            "usageState": self.usage_state,
            "resourceStatus": self.resource_status,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return _filter_top_level_fields(payload, fields_filter)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_native_links()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "related_party" in vals or "name" in vals or "partner_id" in vals or "stock_location_id" in vals:
            self._sync_native_links()
        self._notify("update")
        return res

    def unlink(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        payloads = [rec.to_tmf_json(host_url=base_url) for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
