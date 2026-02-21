# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields

from .common import _as_dict, _as_list, _filter_top_level_fields

API_BASE = "/tmf-api/resourcePoolManagement/v5/resourcePool"


class TMFAvailabilityCheck(models.Model):
    _name = "tmf.resource.pool.availability.check"
    _description = "TMF685 AvailabilityCheck"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)

    tmf_type = fields.Char(required=True, default="AvailabilityCheck")  # @type

    resource_pool_id = fields.Many2one("tmf.resource.pool", required=True, ondelete="cascade", index=True)

    state = fields.Char(required=True, default="acknowledged")
    capacity_demand = fields.Text(required=True, help="JSON: capacityDemand")
    capacity_option = fields.Text(help="JSON list: capacityOption[]")
    error_message = fields.Text(help="JSON: errorMessage")

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")
        rp_id = self.resource_pool_id.tmf_id
        payload = {
            "id": self.tmf_id,
            "href": self.href or f"{host_url}{API_BASE}/{rp_id}/availabilityCheck/{self.tmf_id}",
            "@type": self.tmf_type,
            "state": self.state,
            "capacityDemand": _as_dict(self.capacity_demand) or {},
            "capacityOption": _as_list(self.capacity_option) or None,
            "errorMessage": self.error_message and __import__("json").loads(self.error_message) or None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return _filter_top_level_fields(payload, fields_filter)
