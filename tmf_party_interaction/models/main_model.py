# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid

API_BASE = "/tmf-api/partyInteractionManagement/v5"
RESOURCE = "partyInteraction"

def _as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    return []


class TMFPartyInteraction(models.Model):
    _name = "tmf.party.interaction"
    _description = "TMF683 PartyInteraction"
    _inherit = ["tmf.model.mixin"]

    # Core TMF fields
    creation_date = fields.Datetime(string="creationDate")
    description = fields.Char(string="description")

    direction = fields.Char(string="direction", required=True)
    reason = fields.Char(string="reason", required=True)

    status = fields.Char(string="status")
    status_change_date = fields.Datetime(string="statusChangeDate")

    interaction_date = fields.Json(string="interactionDate")

    # TMF683 requires relatedChannel object (not "channel" string) :contentReference[oaicite:5]{index=5}
    related_channel = fields.Json(string="relatedChannel", required=True)

    # Optional complex fields (store as JSON to avoid schema/type mismatches)
    attachment = fields.Json(string="attachment")
    external_identifier = fields.Json(string="externalIdentifier")
    interaction_item = fields.Json(string="interactionItem")
    interaction_relationship = fields.Json(string="interactionRelationship")
    note = fields.Json(string="note")
    related_party = fields.Json(string="relatedParty")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")

    tmf_type = fields.Char(string="@type", required=True, default="PartyInteraction")

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        parties = _as_list(self.related_party)
        if not parties:
            return self.env["res.partner"]

        Partner = self.env["res.partner"].sudo()
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            pname = party.get("name")
            if pid:
                partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
                if not partner and str(pid).isdigit():
                    partner = Partner.browse(int(pid))
                if partner and partner.exists():
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
        return self.env["res.partner"]

    def _sync_partner_link(self):
        for rec in self:
            if rec.partner_id and rec.partner_id.exists():
                continue
            partner = rec._resolve_partner_from_related_party()
            if partner and partner.exists():
                rec.partner_id = partner.id

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PartyInteractionCreateEvent",
            "update": "PartyInteractionAttributeValueChangeEvent",
            "delete": "PartyInteractionDeleteEvent",
        }
        if payloads is None:
            host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("partyInteraction", event_name, payload)
            except Exception:
                continue

    def _get_tmf_api_path(self):
        return f"{API_BASE}/{RESOURCE}"

    def to_tmf_json(self, host_url=""):
        self.ensure_one()
        host_url = (host_url or "").rstrip("/")
        href = self.href or f"{host_url}{API_BASE}/{RESOURCE}/{self.tmf_id}"

        payload = {
            "id": self.tmf_id,
            "href": href,
            "@type": self.tmf_type or "PartyInteraction",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "direction": self.direction,
            "reason": self.reason,
            "status": None if self.status in (None, "") else str(self.status),
            "statusChangeDate": self.status_change_date.isoformat() if self.status_change_date else None,
            "interactionDate": self.interaction_date,
            "relatedChannel": self.related_channel,
            "attachment": self.attachment,
            "externalIdentifier": _as_list(self.external_identifier),
            "interactionItem": self.interaction_item,
            "interactionRelationship": self.interaction_relationship,
            "note": self.note,
            "relatedParty": self.related_party,
        }
        if payload.get("interactionDate") in ("", None):
            payload.pop("interactionDate", None)

        return {k: v for k, v in payload.items() if v is not None}

    @api.model_create_multi
    def create(self, vals_list):
        # ensure tmf_id exists if your mixin doesn't set it (safe)
        for vals in vals_list:
            vals.setdefault("tmf_id", str(uuid.uuid4()))
        recs = super().create(vals_list)
        recs._sync_partner_link()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "related_party" in vals or "partner_id" in vals:
            self._sync_partner_link()
        self._notify("update")
        return res

    def unlink(self):
        host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
