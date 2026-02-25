# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import uuid

class TMF672UserRole(models.Model):
    _name = "tmf672.user.role"
    _description = "TMF672 UserRole"
    _inherit = ["tmf.model.mixin"]

    tmf_id = fields.Char(string="id", required=True, default=lambda self: str(uuid.uuid4()), index=True)
    href = fields.Char(compute="_compute_href", store=True, index=True)
    tmf_type = fields.Char(string="@type", default="UserRole")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    involvement_role = fields.Char(string="involvementRole")
    entitlement_json = fields.Text(string="entitlement")  # Entitlement[*]

    _sql_constraints = [
        ("tmf672_user_role_tmf_id_uniq", "unique(tmf_id)", "TMF672 UserRole id must be unique."),
    ]

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "UserRoleCreateEvent",
            "update": "UserRoleAttributeValueChangeEvent",
            "delete": "UserRoleDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.tmf_to_payload() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("userRole", event_name, payload)
            except Exception:
                continue

    def _compute_href(self):
        for r in self:
            r.href = f"/tmf-api/userRolePermissionManagement/v4/userRole/{r.tmf_id}"

    def tmf_to_payload(self, api_base_path="/tmf-api/userRolePermissionManagement/v4"):
        self.ensure_one()
        rid = self.tmf_id
        payload = {
            "id": rid,
            "href": f"{api_base_path}/userRole/{rid}",
            "@type": self.tmf_type or "UserRole",
            # CTK expects this to exist and be an array
            "entitlement": json.loads(self.entitlement_json) if self.entitlement_json else [],
        }
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        if self.involvement_role:
            payload["involvementRole"] = self.involvement_role
        return payload

    @classmethod
    def tmf_create_from_payload(cls, env, payload):
        vals = {
            "tmf_id": payload.get("id") or str(uuid.uuid4()),
            "tmf_type": payload.get("@type") or "UserRole",
            "base_type": payload.get("@baseType"),
            "schema_location": payload.get("@schemaLocation"),
            "involvement_role": payload.get("involvementRole"),
            "entitlement_json": json.dumps(payload.get("entitlement"), ensure_ascii=False) if payload.get("entitlement") is not None else json.dumps([]),
        }
        return env["tmf672.user.role"].sudo().create(vals)

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
        payloads = [rec.tmf_to_payload() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
