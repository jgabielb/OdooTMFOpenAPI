# -*- coding: utf-8 -*-
import uuid
import json
from odoo import models, fields

from .common import _as_list, _filter_top_level_fields

API_BASE = "/tmf-api/resourcePoolManagement/v5/capacitySpecification"


class TMFCapacitySpecification(models.Model):
    _name = "tmf.capacity.specification"
    _description = "TMF685 CapacitySpecification"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)

    tmf_type = fields.Char(required=True, default="CapacitySpecification")  # @type

    # Store as JSON string for flexibility
    capacity_characteristic_specification = fields.Text(
        help="JSON list: capacityCharacteristicSpecification[]"
    )
    external_identifier = fields.Text(help="JSON: externalIdentifier")
    related_capacity_specification = fields.Text(help="JSON list: relatedCapacitySpecification[]")

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")
        payload = {
            "id": self.tmf_id,
            "href": self.href or f"{host_url}{API_BASE}/{self.tmf_id}",
            "@type": self.tmf_type,
            "capacityCharacteristicSpecification": _as_list(self.capacity_characteristic_specification) or [],
            "externalIdentifier": json.loads(self.external_identifier) if self.external_identifier else None,
            "relatedCapacitySpecification": _as_list(self.related_capacity_specification) or [],
        }

        # remove nulls
        payload = {k: v for k, v in payload.items() if v is not None}
        return _filter_top_level_fields(payload, fields_filter)
