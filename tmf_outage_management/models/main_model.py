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


class TMFOutage(models.Model):
    _name = "tmf.outage"
    _description = "TMF777 Outage"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    reason = fields.Char(string="reason", required=True)
    state = fields.Char(string="state")
    is_planned = fields.Boolean(string="isPlanned", required=True)
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    project_task_id = fields.Many2one("project.task", string="Project Task", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/outageManagement/v5/outage"

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

    def _sync_native_links(self):
        env_task = self.env["project.task"].sudo()
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            if rec.project_task_id and rec.project_task_id.exists():
                continue
            try:
                domain = [("name", "=", rec.name or rec.tmf_id)]
                if rec.partner_id:
                    domain = [("partner_id", "=", rec.partner_id.id), ("name", "=", rec.name or rec.tmf_id)]
                task = env_task.search(domain, limit=1)
                if not task:
                    vals = {"name": rec.name or f"Outage:{rec.tmf_id}", "description": rec.description or rec.reason}
                    if rec.partner_id:
                        vals["partner_id"] = rec.partner_id.id
                    task = env_task.create(vals)
                rec.project_task_id = task.id
            except Exception:
                pass

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        payload["name"] = self.name
        payload["reason"] = self.reason
        payload["isPlanned"] = bool(self.is_planned)
        if self.description is not None:
            payload["description"] = self.description
        if self.state is not None:
            payload["state"] = self.state
        payload["@type"] = self.tmf_type_value or payload.get("@type") or "Outage"
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("reason", "reason"),
            ("state", "state"),
            ("isPlanned", "is_planned"),
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
                api_name="outage",
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
        state_changed = "state" in vals
        res = super().write(vals)
        if "payload_json" in vals or "name" in vals or "description" in vals or "partner_id" in vals or "project_task_id" in vals:
            self._sync_native_links()
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="outage",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

