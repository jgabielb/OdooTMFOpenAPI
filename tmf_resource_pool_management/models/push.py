# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields

from .common import _as_list, _filter_top_level_fields

API_BASE = "/tmf-api/resourcePoolManagement/v5/resourcePool"


class TMFPush(models.Model):
    _name = "tmf.resource.pool.push"
    _description = "TMF685 Push"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)

    tmf_type = fields.Char(required=True, default="Push")  # @type

    resource_pool_id = fields.Many2one("tmf.resource.pool", required=True, ondelete="cascade", index=True)

    state = fields.Char(required=True, default="acknowledged")
    error_message = fields.Text(help="JSON: errorMessage")
    pushed_resource = fields.Text(required=True, help="JSON list: pushedResource[]")

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")
        rp_id = self.resource_pool_id.tmf_id
        base_url = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        href_value = self.href or f"{host_url}{API_BASE}/{rp_id}/push/{self.tmf_id}"
        if isinstance(href_value, str) and href_value.startswith("/"):
            href_value = f"{base_url}{href_value}" if base_url else href_value
        payload = {
            "id": str(self.tmf_id),
            "href": href_value,
            "@type": self.tmf_type,
            "state": self.state,
            "errorMessage": self.error_message and __import__("json").loads(self.error_message) or None,
            "pushedResource": _as_list(self.pushed_resource) or [],
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return _filter_top_level_fields(payload, fields_filter)
