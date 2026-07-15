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


class TMFC046WorkforceManagement(models.Model):
    _inherit = "tmf.work"

    tmfc046_related_partner_ids = fields.Many2many(
        "res.partner", "tmfc046_partner_rel", "rec_id", "partner_id",
        string="TMFC046 Related Partners",
    )
    tmfc046_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmfc046_party_role_rel", "rec_id", "party_role_id",
        string="TMFC046 Party Roles",
    )

    def _tmfc046_resolve_refs(self):
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
                    updates["tmfc046_related_partner_ids"] = [(6, 0, p.ids)]
            if role_refs:
                r = PartyRole.search([("tmf_id", "in", role_refs)])
                if r:
                    updates["tmfc046_party_role_ids"] = [(6, 0, r.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc046_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and "related_party_json" in vals:
            try:
                self._tmfc046_resolve_refs()
            except Exception:
                pass
        return res


class TMFC046WiringTools(models.AbstractModel):
    _name = "tmfc046.wiring.tools"
    _description = "TMFC046 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        Rec = self.env["tmf.work"].sudo()
        Rec.search([])._tmfc046_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_process_flow_event(self, payload):
        """TMF701 processFlow/taskFlow events: sync local flow state by tmf_id."""
        resource = payload or {}
        event = resource.get("event")
        if isinstance(event, dict):
            for value in event.values():
                if isinstance(value, dict) and value.get("id"):
                    resource = value
                    break
        ref_id = str(resource.get("id") or "").strip()
        state = resource.get("state")
        if not ref_id or not state:
            return False
        for model in ("tmf.process.flow", "tmf.task.flow"):
            rec = self.env[model].sudo().search([("tmf_id", "=", ref_id)], limit=1)
            if rec:
                try:
                    rec.with_context(skip_tmf_wiring=True).write({"state": state})
                except Exception:
                    pass
                break
        return True
