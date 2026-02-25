import json
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None and v is not False}


class TMFResourceUsageMixin(models.AbstractModel):
    _name = "tmf.resource.usage.mixin"
    _description = "TMF771 Resource Usage Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    usage_date = fields.Char(string="usageDate")
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    _api_name = None
    _default_type = None

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        if self.name is not None:
            payload["name"] = self.name
        if self.description is not None:
            payload["description"] = self.description
        if self.usage_date is not None:
            payload["usageDate"] = self.usage_date
        payload["@type"] = self.tmf_type_value or payload.get("@type") or self._default_type
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("usageDate", "usage_date"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=self._api_name,
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        api_name = self._api_name
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name=api_name,
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFResourceUsage(models.Model):
    _name = "tmf.resource.usage"
    _description = "TMF771 ResourceUsage"
    _inherit = ["tmf.resource.usage.mixin"]

    _api_name = "resourceUsage"
    _default_type = "ResourceUsage"

    def _get_tmf_api_path(self):
        return "/resourceUsageManagement/v5/resourceUsage"


class TMFResourceUsageSpecification(models.Model):
    _name = "tmf.resource.usage.specification"
    _description = "TMF771 ResourceUsageSpecification"
    _inherit = ["tmf.resource.usage.mixin"]

    _api_name = "resourceUsageSpecification"
    _default_type = "ResourceUsageSpecification"

    def _get_tmf_api_path(self):
        return "/resourceUsageManagement/v5/resourceUsageSpecification"
