# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models


def _loads(v):
    if v in (None, False, ""):
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return None


def _collect(items):
    party, roles = [], []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("id") or "").strip()
        if not rid:
            continue
        if it.get("@type") in ("PartyRole", "PartyRoleRef"):
            roles.append(rid)
        else:
            party.append(rid)
    return party, roles


class TMFC041AnomalyManagement(models.Model):
    _inherit = "tmf.incident"

    tmfc041_related_partner_ids = fields.Many2many(
        "res.partner", "tmfc041_partner_rel", "rec_id", "partner_id",
        string="TMFC041 Related Partners",
    )
    tmfc041_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmfc041_party_role_rel", "rec_id", "party_role_id",
        string="TMFC041 Party Roles",
    )
    tmfc041_alarm_ids = fields.Many2many(
        "tmf.alarm", "tmfc041_alarm_rel", "rec_id", "alarm_id",
        string="TMFC041 Correlated Alarms (TMF642)",
    )
    tmfc041_ai_resource_ids = fields.Many2many(
        "tmf.ai.management.resource", "tmfc041_ai_rel", "rec_id", "ai_id",
        string="TMFC041 AI Sources (TMF915)",
    )

    def _tmfc041_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        for rec in self:
            items = _loads(rec.related_party_json) or []
            if isinstance(items, dict):
                # payload_json can be a full object; look for relatedParty key
                items = items.get("relatedParty") or []
            party_refs, role_refs = _collect(items)
            updates = {}
            if party_refs:
                p = Partner.search([("tmf_id", "in", party_refs)])
                if p:
                    updates["tmfc041_related_partner_ids"] = [(6, 0, p.ids)]
            if role_refs:
                r = PartyRole.search([("tmf_id", "in", role_refs)])
                if r:
                    updates["tmfc041_party_role_ids"] = [(6, 0, r.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    def _tmfc041_notify_anomaly(self, action):
        """TMFC041 YAML publishes TMF751 anomaly events for incident mutations."""
        for rec in self:
            try:
                payload = rec.to_tmf_json() if hasattr(rec, "to_tmf_json") else {
                    "id": rec.tmf_id or str(rec.id), "@type": "Anomaly"}
                self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                    api_name="anomaly", event_type=action, resource_json=payload)
            except Exception:
                pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc041_resolve_refs()
            except Exception:
                pass
            recs._tmfc041_notify_anomaly("create")
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "status" in vals
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            if "related_party_json" in vals:
                try:
                    self._tmfc041_resolve_refs()
                except Exception:
                    pass
            self._tmfc041_notify_anomaly("state_change" if state_changed else "update")
        return res


class TMFC041WiringTools(models.AbstractModel):
    _name = "tmfc041.wiring.tools"
    _description = "TMFC041 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        Rec = self.env["tmf.incident"].sudo()
        Rec.search([])._tmfc041_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    def _extract_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        event = payload.get("event")
        if isinstance(event, dict):
            if isinstance(event.get("resource"), dict):
                return event["resource"]
            for v in event.values():
                if isinstance(v, dict) and v.get("id"):
                    return v
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    @api.model
    def _handle_alarm_event(self, payload):
        """TMF642 alarm C/state/D: sync alarm state and correlate to incidents."""
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if not ref_id:
            return False
        alarm = self.env["tmf.alarm"].sudo().search([("tmf_id", "=", ref_id)], limit=1)
        if alarm:
            state = resource.get("state") or resource.get("status")
            if state and "state" in alarm._fields:
                try:
                    alarm.with_context(skip_tmf_wiring=True).write({"state": state})
                except Exception:
                    pass
            # correlate: link alarm into incidents whose payload references it
            Incident = self.env["tmf.incident"].sudo()
            for inc in Incident.search([]):
                blob = "%s" % (getattr(inc, "root_cause_json", "") or "",)
                if ref_id in blob and alarm.id not in inc.tmfc041_alarm_ids.ids:
                    inc.with_context(skip_tmf_wiring=True).write(
                        {"tmfc041_alarm_ids": [(4, alarm.id)]})
        return True

    @api.model
    def _handle_ai_management_event(self, payload):
        """TMF915 AI contract/model events: sync local AI resource state."""
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if not ref_id:
            return False
        rec = self.env["tmf.ai.management.resource"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1)
        if rec:
            state = resource.get("state") or resource.get("status")
            for field in ("state", "status", "lifecycle_status"):
                if state and field in rec._fields:
                    try:
                        rec.with_context(skip_tmf_wiring=True).write({field: state})
                    except Exception:
                        pass
                    break
        return True
