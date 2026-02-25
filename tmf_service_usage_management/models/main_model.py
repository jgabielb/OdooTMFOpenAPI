import json
from datetime import datetime, timezone
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None}


class TMFServiceUsage(models.Model):
    _name = "tmf.service.usage"
    _description = "TMF727 ServiceUsage"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    usage_date = fields.Char(string="usageDate")
    usage_type = fields.Char(string="usageType")
    status = fields.Char(string="status", required=True)

    related_party_json = fields.Text(string="relatedParty")
    service_json = fields.Text(string="service")
    usage_characteristic_json = fields.Text(string="usageCharacteristic")
    usage_specification_json = fields.Text(string="usageSpecification")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/serviceUsage/v4/serviceUsage"

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "usageDate": self.usage_date,
            "usageType": self.usage_type,
            "status": self.status,
            "relatedParty": _loads(self.related_party_json),
            "service": _loads(self.service_json),
            "usageCharacteristic": _loads(self.usage_characteristic_json),
            "usageSpecification": _loads(self.usage_specification_json),
            "@type": self.tmf_type_value or "ServiceUsage",
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("usageDate", "usage_date"),
            ("usageType", "usage_type"),
            ("status", "status"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("relatedParty", "related_party_json"),
            ("service", "service_json"),
            ("usageCharacteristic", "usage_characteristic_json"),
            ("usageSpecification", "usage_specification_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="serviceUsage",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("status", vals.get("status") or "received")
            vals.setdefault("usage_date", vals.get("usage_date") or self._now_iso())
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        status_changed = "status" in vals
        res = super().write(vals)
        if status_changed:
            for rec in self:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="serviceUsage",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

