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
    _name = "tmf.iot.agent.device.resource"
    _description = "TMF908 IoT Agent and Device Management Resource"
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
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    device_id = fields.Many2one("tmf.device", string="Device", ondelete="set null")

    def _get_tmf_api_path(self):
        self.ensure_one()
        return "/tmf-api/iotdevicemanagement/v4/%s" % (self.resource_type or "iotDevice")

    def _resolve_partner(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        refs = payload.get("relatedParty")
        if isinstance(refs, dict):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        env_partner = self.env["res.partner"].sudo()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (ref.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _resolve_device(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        env_device = self.env["tmf.device"].sudo()
        rid = payload.get("id")
        if rid:
            rec = env_device.search([("tmf_id", "=", str(rid))], limit=1)
            if rec:
                return rec
        name = payload.get("name") or self.name
        if name:
            return env_device.search([("name", "=", name)], limit=1)
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            device = rec._resolve_device()
            if device:
                rec.device_id = device.id

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
        payload["@type"] = self.tmf_type_value or payload.get("@type") or "IotDevice"
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
        recs._sync_native_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "status" in vals or "lifecycle_status" in vals
        res = super().write(vals)
        if "payload_json" in vals or "name" in vals or "partner_id" in vals or "device_id" in vals:
            self._sync_native_links()
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

