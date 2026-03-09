# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api


class TMFPartnership(models.Model):
    _name = "tmf.partnership"
    _description = "TMF668 Partnership"
    _rec_name = "name"

    tmf_id = fields.Char(string="TMF id", index=True, required=True)
    href = fields.Char(string="href", index=True)
    name = fields.Char(required=True)
    description = fields.Text()

    specification_json = fields.Text(string="specification")  # ref object as JSON string
    partner_json = fields.Text(string="partner")              # list as JSON string
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    specification_id = fields.Many2one("tmf.partnership.specification", string="Specification", ondelete="set null")

    _sql_constraints = [
        ("tmf_id_unique", "unique(tmf_id)", "TMF id must be unique."),
    ]

    def _json_load(self, value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except Exception:
            return default

    def _resolve_partner_from_payload(self):
        self.ensure_one()
        data = self._json_load(self.partner_json, [])
        if isinstance(data, dict):
            data = [data]
        env_partner = self.env["res.partner"].sudo()
        for item in data:
            if not isinstance(item, dict):
                continue
            rid = item.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (item.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _resolve_spec_from_payload(self):
        self.ensure_one()
        data = self._json_load(self.specification_json, {})
        if not isinstance(data, dict):
            return False
        env_spec = self.env["tmf.partnership.specification"].sudo()
        rid = data.get("id")
        if rid:
            spec = env_spec.search([("tmf_id", "=", str(rid))], limit=1)
            if spec:
                return spec
        name = (data.get("name") or "").strip()
        if name:
            return env_spec.search([("name", "=", name)], limit=1)
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner_from_payload()
            if partner and rec.partner_id.id != partner.id:
                rec.with_context(skip_tmf_native_sync=True).write({"partner_id": partner.id})
            spec = rec._resolve_spec_from_payload()
            if spec and rec.specification_id.id != spec.id:
                rec.with_context(skip_tmf_native_sync=True).write({"specification_id": spec.id})

    def _to_tmf_json(self):
        return {
            "id": self.tmf_id,
            "href": self.href or f"/tmf-api/partnershipManagement/v4/partnership/{self.tmf_id}",
            "name": self.name,
            "description": self.description,
            "@type": "Partnership",
        }

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PartnershipCreateEvent",
            "update": "PartnershipAttributeValueChangeEvent",
            "delete": "PartnershipDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec._to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("partnership", event_name, payload)
            except Exception:
                continue

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_native_links()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_tmf_native_sync"):
            return res
        if (
            "partner_json" in vals
            or "specification_json" in vals
        ):
            self._sync_native_links()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec._to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
