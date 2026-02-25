# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
from datetime import datetime, timezone
import uuid


def _uuid():
    return str(uuid.uuid4())

def _utcnow_id():
    # matches your example: 2026-02-03T14:47:34Z
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TMFPromotion(models.Model):
    _name = "tmf.promotion"
    _description = "TMF671 Promotion"
    _order = "write_date desc"

    # TMF fields
    tmf_id = fields.Char(string="id", index=True, required=True, copy=False)
    href = fields.Char(string="href", index=True, copy=False)
    name = fields.Char(required=True)
    description = fields.Text()
    last_update = fields.Datetime(string="lastUpdate")
    lifecycle_status = fields.Char(string="lifecycleStatus")  # draft/test/waitForApproval/release/suspend/retirement (suggested) :contentReference[oaicite:1]{index=1}
    promotion_type = fields.Char(string="promotionType")      # Award/Discount/Reduction (suggested) :contentReference[oaicite:2]{index=2}

    # TMF meta
    base_type = fields.Char(string="@baseType", default="Promotion")
    schema_location = fields.Char(string="@schemaLocation")
    tmf_type = fields.Char(string="@type", default="Promotion")

    # Complex structures as JSON text
    pattern_json = fields.Text(string="pattern")   # PromotionPattern[*] :contentReference[oaicite:3]{index=3}
    valid_for_json = fields.Text(string="validFor")  # TimePeriod :contentReference[oaicite:4]{index=4}

    _sql_constraints = [
        ("tmf_id_uniq", "unique(tmf_id)", "TMF671: id must be unique."),
    ]

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PromotionCreateEvent",
            "update": "PromotionAttributeValueChangeEvent",
            "delete": "PromotionDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf("/tmf-api/promotionManagement/v4") for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("promotion", event_name, payload)
            except Exception:
                continue

    @api.constrains("pattern_json", "valid_for_json")
    def _check_json(self):
        for rec in self:
            for fname in ("pattern_json", "valid_for_json"):
                val = getattr(rec, fname)
                if val:
                    try:
                        json.loads(val)
                    except Exception:
                        raise ValidationError(_("TMF671: %s must be valid JSON.") % fname)

    def to_tmf(self, api_base):
        """Return TMF JSON representation."""
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href or f"{api_base}/promotion/{self.tmf_id}",
            "name": self.name,
            "@type": self.tmf_type or "Promotion",
        }
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        if self.description is not None:
            desc = payload.get("description")
            payload["description"] = desc if isinstance(desc, str) else None
        if self.last_update:
            dt = fields.Datetime.to_datetime(self.last_update)
            payload["lastUpdate"] = dt.replace(microsecond=0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        if self.lifecycle_status:
            payload["lifecycleStatus"] = self.lifecycle_status
        if self.promotion_type:
            payload["promotionType"] = self.promotion_type

        if self.pattern_json:
            payload["pattern"] = json.loads(self.pattern_json)
        if self.valid_for_json:
            payload["validFor"] = json.loads(self.valid_for_json)

        return payload

    @api.model
    def from_tmf_create(self, payload, api_base):
        """
        TMF671 create:
        Mandatory: name :contentReference[oaicite:5]{index=5}
        """
        name = payload.get("name")
        if not name:
            raise ValidationError(_("TMF671 POST: 'name' is mandatory."))

        tmf_id = payload.get("id") or str(uuid.uuid4())

        vals = {
            "tmf_id": tmf_id,
            "name": name,
            "description": payload.get("description"),
            "lifecycle_status": payload.get("lifecycleStatus") or "draft",
            "promotion_type": payload.get("promotionType"),
            "tmf_type": payload.get("@type") or "Promotion",
            "base_type": payload.get("@baseType") or "Promotion",
            "schema_location": payload.get("@schemaLocation"),
            "last_update": fields.Datetime.now(),
        }

        if payload.get("pattern") is not None:
            vals["pattern_json"] = json.dumps(payload.get("pattern"), ensure_ascii=False)
        if payload.get("validFor") is not None:
            vals["valid_for_json"] = json.dumps(payload.get("validFor"), ensure_ascii=False)

        rec = self.create(vals)
        rec.href = f"{api_base}/promotion/{rec.tmf_id}"
        return rec

    def apply_merge_patch(self, patch, api_base):
        """
        PATCH /promotion/{id}:
        - merge-patch mandatory :contentReference[oaicite:6]{index=6}
        - non-patchable: id, href, pattern ids, @baseType, @schemaLocation, @type (per guide) :contentReference[oaicite:7]{index=7}
        """
        self.ensure_one()

        # Disallow top-level changes
        blocked = {"id", "href", "@baseType", "@schemaLocation", "@type"}
        for k in patch.keys():
            if k in blocked:
                raise ValidationError(_("TMF671 PATCH: '%s' is not patchable.") % k)

        # Disallow patching of internal ids under pattern per guide :contentReference[oaicite:8]{index=8}
        # (we enforce by rejecting any merge-patch that tries to include them)
        if "pattern" in patch:
            def _contains_ids(obj):
                if isinstance(obj, dict):
                    if "id" in obj:
                        return True
                    return any(_contains_ids(v) for v in obj.values())
                if isinstance(obj, list):
                    return any(_contains_ids(i) for i in obj)
                return False

            if _contains_ids(patch.get("pattern")):
                raise ValidationError(_("TMF671 PATCH: pattern.*.id / criteriaGroup.id / criteria.id / action.id are not patchable."))

        vals = {}
        if "name" in patch:
            vals["name"] = patch.get("name")
        if "description" in patch:
            vals["description"] = patch.get("description")
        if "lifecycleStatus" in patch:
            vals["lifecycle_status"] = patch.get("lifecycleStatus")
        if "promotionType" in patch:
            vals["promotion_type"] = patch.get("promotionType")
        if "validFor" in patch:
            vals["valid_for_json"] = json.dumps(patch.get("validFor"), ensure_ascii=False) if patch.get("validFor") is not None else False
        if "pattern" in patch:
            vals["pattern_json"] = json.dumps(patch.get("pattern"), ensure_ascii=False) if patch.get("pattern") is not None else False

        # server-managed lastUpdate
        vals["last_update"] = fields.Datetime.now()

        self.write(vals)
        if not self.href:
            self.href = f"{api_base}/promotion/{self.tmf_id}"
        return self

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
        payloads = [rec.to_tmf("/tmf-api/promotionManagement/v4") for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
