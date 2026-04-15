# -*- coding: utf-8 -*-
"""TMFC010 ResourceCatalogManagement wiring tools.

Reconciles TMF634 ResourceSpecification side-car refs against TMF632
Party, TMF669 PartyRole, and peer ResourceSpecification records. Mirrors
the TMFC006 pattern (side-car JSON + relational fields, best-effort
listeners, never raises).
"""

import json

from odoo import api, models


def _loads(value):
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _resolve_ids(env, model, items):
    ref_ids = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("id") or "").strip()
        if ref_id:
            ref_ids.append(ref_id)
    if not ref_ids:
        return []
    return env[model].sudo().search([("tmf_id", "in", ref_ids)]).ids


def _extract_resource_id(payload):
    if not isinstance(payload, dict):
        return ""
    ev = payload.get("event")
    if isinstance(ev, dict) and isinstance(ev.get("resource"), dict):
        return str(ev["resource"].get("id") or "").strip()
    if isinstance(payload.get("resource"), dict):
        return str(payload["resource"].get("id") or "").strip()
    return str(payload.get("id") or "").strip()


class TMFC010WiringTools(models.AbstractModel):
    _name = "tmfc010.wiring.tools"
    _description = "TMFC010 Wiring Tools - Resource Catalog wiring"

    @api.model
    def _resolve_resource_spec_references(self, specs=None):
        ResourceSpec = self.env["tmf.resource.specification"].sudo()
        if not specs:
            specs = ResourceSpec.search([
                "|", "|",
                ("tmfc010_related_party_json", "!=", False),
                ("tmfc010_resource_spec_rel_json", "!=", False),
                ("raw_json", "!=", False),
            ])
        ctx = {"skip_tmf_wiring": True}
        for spec in specs:
            updates = {}
            raw = _loads(spec.raw_json) or {}
            related_party = _loads(spec.tmfc010_related_party_json) or raw.get("relatedParty") or []
            rel_spec = _loads(spec.tmfc010_resource_spec_rel_json) or raw.get("resourceSpecRelationship") or []

            if related_party and not spec.tmfc010_related_partner_ids:
                items = [
                    i for i in related_party
                    if isinstance(i, dict)
                    and i.get("@type") not in ("PartyRole", "PartyRoleRef")
                ]
                ids = _resolve_ids(self.env, "res.partner", items)
                if ids:
                    updates["tmfc010_related_partner_ids"] = [(6, 0, ids)]

            if related_party and not spec.tmfc010_party_role_ids:
                items = [
                    i for i in related_party
                    if isinstance(i, dict)
                    and i.get("@type") in ("PartyRole", "PartyRoleRef")
                ]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["tmfc010_party_role_ids"] = [(6, 0, ids)]

            if rel_spec and not spec.tmfc010_related_spec_ids:
                ids = _resolve_ids(self.env, "tmf.resource.specification", rel_spec)
                ids = [i for i in ids if i != spec.id]
                if ids:
                    updates["tmfc010_related_spec_ids"] = [(6, 0, ids)]

            if updates:
                spec.with_context(**ctx).write(updates)
        return True

    @api.model
    def _handle_party_event(self, payload):
        try:
            ref_id = _extract_resource_id(payload or {})
            if not ref_id:
                return True
            ResourceSpec = self.env["tmf.resource.specification"].sudo()
            specs = ResourceSpec.search([("tmfc010_related_party_json", "ilike", ref_id)])
            if specs:
                self._resolve_resource_spec_references(specs)
        except Exception:
            pass
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        try:
            ref_id = _extract_resource_id(payload or {})
            if not ref_id:
                return True
            ResourceSpec = self.env["tmf.resource.specification"].sudo()
            specs = ResourceSpec.search([("tmfc010_related_party_json", "ilike", ref_id)])
            if specs:
                self._resolve_resource_spec_references(specs)
        except Exception:
            pass
        return True
