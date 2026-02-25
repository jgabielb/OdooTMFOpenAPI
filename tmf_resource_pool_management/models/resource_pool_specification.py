# -*- coding: utf-8 -*-
import uuid
import json
from odoo import models, fields

from .common import _as_list, _filter_top_level_fields

API_BASE = "/tmf-api/resourcePoolManagement/v5/resourcePoolSpecification"


class TMFResourcePoolSpecification(models.Model):
    _name = "tmf.resource.pool.specification"
    _description = "TMF685 ResourcePoolSpecification"
    _rec_name = "name"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)

    tmf_type = fields.Char(required=True, default="ResourcePoolSpecification")  # @type

    name = fields.Char(required=True)
    description = fields.Text()

    # mandatory in response per conformance: capacitySpecification[] :contentReference[oaicite:1]{index=1}
    capacity_specification = fields.Text(required=True, help="JSON list: capacitySpecificationRef[]")

    attachment = fields.Text(help="JSON list: attachment[]")
    external_identifier = fields.Text(help="JSON: externalIdentifier")
    feature_specification = fields.Text(help="JSON list: featureSpecification[]")
    related_party = fields.Text(help="JSON list: relatedParty[]")
    target_resource_schema = fields.Text(help="JSON: targetResourceSchema")

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
            "capacitySpecification": _as_list(self.capacity_specification) or [],
            "attachment": _as_list(self.attachment) or None,
            "externalIdentifier": json.loads(self.external_identifier) if self.external_identifier else None,
            "featureSpecification": _as_list(self.feature_specification) or None,
            "relatedParty": _as_list(self.related_party) or None,
            "targetResourceSchema": json.loads(self.target_resource_schema) if self.target_resource_schema else None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return _filter_top_level_fields(payload, fields_filter)
