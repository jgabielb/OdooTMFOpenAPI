# -*- coding: utf-8 -*-
import uuid
import json
from odoo import models, fields

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

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")
        payload = {
            "id": self.tmf_id,
            "href": self.href or f"{host_url}{API_BASE}/{self.tmf_id}",
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
