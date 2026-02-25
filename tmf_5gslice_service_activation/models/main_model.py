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


class TMFGenericResource(models.Model):
    _name = "tmf.5gslice.service.activation.resource"
    _description = "TMF924 DCS 5G Slice Service Activation Resource"
    _inherit = ["tmf.model.mixin"]

    resource_type = fields.Char(string="resourceType", required=True, index=True)
    name = fields.Char(string="name")
    description = fields.Char(string="description")
    state = fields.Char(string="state")
    status = fields.Char(string="status")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        self.ensure_one()
        return "/tmf-api/ServiceActivationAndConfiguration/v4/%s" % (self.resource_type or "service")

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        if self.name is not None:
            payload["name"] = self.name
        if self.description is not None:
            payload["description"] = self.description
        if self.state is not None:
            payload["state"] = self.state
        if self.status is not None:
            payload["status"] = self.status
        if self.lifecycle_status is not None:
            payload["lifecycleStatus"] = self.lifecycle_status
        payload["@type"] = self.tmf_type_value or payload.get("@type") or "Service"
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, resource_type=None, partial=False):
        vals = {"payload_json": _dumps(data)}
        if resource_type:
            vals["resource_type"] = resource_type
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("state", "state"),
            ("status", "status"),
            ("lifecycleStatus", "lifecycle_status"),
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
                api_name=rec.resource_type,
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
        state_changed = "state" in vals or "status" in vals or "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [(rec.resource_type, rec.to_tmf_json()) for rec in self]
        res = super().unlink()
        for resource_type, payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name=resource_type,
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

