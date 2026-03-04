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
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", ondelete="set null")

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

    def _resolve_partner_ref(self):
        self.ensure_one()
        refs = _loads(self.related_party_json)
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

    def _resolve_sale_order_ref(self):
        self.ensure_one()
        service = _loads(self.service_json)
        if not isinstance(service, dict):
            return False
        rid = service.get("id")
        if not rid:
            return False
        env_so = self.env["sale.order"].sudo()
        so = env_so.search([("client_order_ref", "=", str(rid))], limit=1)
        if so:
            return so
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner_ref()
            if partner:
                rec.partner_id = partner.id
            so = rec._resolve_sale_order_ref()
            if so:
                rec.sale_order_id = so.id

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
        recs._sync_native_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        status_changed = "status" in vals
        res = super().write(vals)
        if (
            "related_party_json" in vals
            or "service_json" in vals
            or "partner_id" in vals
            or "sale_order_id" in vals
        ):
            self._sync_native_links()
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

