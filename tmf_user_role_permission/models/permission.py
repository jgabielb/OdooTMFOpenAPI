# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import uuid
from datetime import datetime, timezone

def _parse_iso_datetime(value):
    if not value:
        return False

    # already datetime?
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()

        # normalize trailing Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        # 1) try Python ISO parser (handles +00:00)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            # 2) fallback formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                raise ValidationError(f"Invalid datetime format: {value}")

    # If timezone-aware, convert to UTC and drop tzinfo (Odoo stores naive UTC)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

    return dt


class TMF672Permission(models.Model):
    _name = "tmf672.permission"
    _description = "TMF672 Permission"
    _inherit = ["tmf.model.mixin"]

    # TMF meta
    tmf_type = fields.Char(string="@type", default="Permission")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    tmf_id = fields.Char(string="id", required=True, default=lambda self: str(uuid.uuid4()), index=True)


    # Core
    name = fields.Char()  # not in spec as mandatory; keep optional for UI
    href = fields.Char(store=True, index=True)
    description = fields.Text()

    creation_date = fields.Datetime()

    # validFor (mandatory on create in spec) :contentReference[oaicite:3]{index=3}
    valid_for_start = fields.Datetime()
    valid_for_end = fields.Datetime()

    # relationships (store as JSON to avoid deep relational modeling)
    granter_json = fields.Text(string="granter")      # RelatedParty
    user_json = fields.Text(string="user", required=True)  # RelatedParty (mandatory) :contentReference[oaicite:4]{index=4}

    # collections
    asset_user_role_json = fields.Text(string="assetUserRole")  # AssetUserRole[*]
    privilege_json = fields.Text(string="privilege")            # Privilege[*]

    _sql_constraints = [("tmf672_permission_tmf_id_uniq", "unique(tmf_id)", "TMF672 Permission id must be unique.")]

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PermissionCreateEvent",
            "update": "PermissionAttributeValueChangeEvent",
            "delete": "PermissionDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.tmf_to_payload() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("permission", event_name, payload)
            except Exception:
                continue

    @api.constrains("user_json", "valid_for_start")
    def _check_mandatory(self):
        for rec in self:
            if not rec.user_json:
                raise ValidationError(_("TMF672: 'user' is mandatory."))
            # validFor is mandatory (start/end can be partially provided depending on your CTK rules;
            # we enforce start as minimal non-null)
            if not rec.valid_for_start:
                raise ValidationError(_("TMF672: 'validFor.startDateTime' is mandatory."))

    # ---------- TMF payload mapping ----------
    def tmf_to_payload(self, api_base_path="/tmf-api/userRolePermissionManagement/v4"):
        self.ensure_one()
        pid = self.tmf_id

        payload = {
            "id": pid,
            "href": f"{api_base_path}/permission/{pid}",
            "@type": self.tmf_type or "Permission",
        }
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location

        if self.creation_date:
            payload["creationDate"] = fields.Datetime.to_string(self.creation_date)
        if self.description:
            payload["description"] = self.description

        # validFor
        valid_for = {}
        if self.valid_for_start:
            valid_for["startDateTime"] = fields.Datetime.to_string(self.valid_for_start)
        if self.valid_for_end:
            valid_for["endDateTime"] = fields.Datetime.to_string(self.valid_for_end)
        if valid_for:
            payload["validFor"] = valid_for

        # related parties
        payload["user"] = json.loads(self.user_json) if self.user_json else None
        if self.granter_json:
            payload["granter"] = json.loads(self.granter_json)

        # arrays
        if self.asset_user_role_json:
            payload["assetUserRole"] = json.loads(self.asset_user_role_json)
        if self.privilege_json:
            payload["privilege"] = json.loads(self.privilege_json)

        return payload

    @classmethod
    def tmf_create_from_payload(cls, env, payload, api_base_path="/tmf-api/userRolePermissionManagement/v4"):
        # Mandatory attributes for Permission create: validFor, user :contentReference[oaicite:5]{index=5}
        valid_for = payload.get("validFor") or {}
        user = payload.get("user")

        if not user:
            raise ValidationError(_("TMF672 POST Permission: 'user' is mandatory."))
        if not valid_for or not valid_for.get("startDateTime"):
            raise ValidationError(_("TMF672 POST Permission: 'validFor.startDateTime' is mandatory."))

        vals = {
            "tmf_type": payload.get("@type") or "Permission",
            "base_type": payload.get("@baseType"),
            "schema_location": payload.get("@schemaLocation"),
            "description": payload.get("description"),
            "creation_date": _parse_iso_datetime(payload.get("creationDate")) or fields.Datetime.now(),
            "valid_for_start": _parse_iso_datetime(valid_for.get("startDateTime")),
            "valid_for_end": _parse_iso_datetime(valid_for.get("endDateTime")),
            "user_json": json.dumps(user, ensure_ascii=False),
            "granter_json": json.dumps(payload.get("granter"), ensure_ascii=False) if payload.get("granter") else False,
            "asset_user_role_json": json.dumps(payload.get("assetUserRole"), ensure_ascii=False) if payload.get("assetUserRole") else False,
            "privilege_json": json.dumps(payload.get("privilege"), ensure_ascii=False) if payload.get("privilege") else False,
        }

        # Additional sub-resource rules (optional unless you enforce):
        # privilege requires manageableAsset, action, function; assetUserRole requires manageableAsset, userRole :contentReference[oaicite:6]{index=6}
        # Keep enforcement light to avoid breaking clients; enable if CTK requires.
        rec = env["tmf672.permission"].sudo().create(vals)
        rec.sudo().write({"href": f"{api_base_path}/permission/{rec.tmf_id}"})
        return rec

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
