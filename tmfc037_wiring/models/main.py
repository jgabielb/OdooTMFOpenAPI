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


class TMFC037ServicePerformanceManagement(models.Model):
    _inherit = "tmf.performance.management.resource"

    tmfc037_related_partner_ids = fields.Many2many(
        "res.partner", "tmfc037_partner_rel", "rec_id", "partner_id",
        string="TMFC037 Related Partners",
    )
    tmfc037_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmfc037_party_role_rel", "rec_id", "party_role_id",
        string="TMFC037 Party Roles",
    )
    tmfc037_service_ids = fields.Many2many(
        "tmf.service", "tmfc037_service_rel", "rec_id", "service_id",
        string="TMFC037 Monitored Services (TMF638)",
    )
    tmfc037_resource_ids = fields.Many2many(
        "stock.lot", "tmfc037_resource_rel", "rec_id", "resource_id",
        string="TMFC037 Monitored Resources (TMF639)",
    )
    tmfc037_slo_ids = fields.Many2many(
        "tmf.service.level.objective", "tmfc037_slo_rel", "rec_id", "slo_id",
        string="TMFC037 Service Level Objectives (TMF657)",
    )
    tmfc037_sls_ids = fields.Many2many(
        "tmf.service.level.specification", "tmfc037_sls_rel", "rec_id", "sls_id",
        string="TMFC037 Service Level Specifications (TMF657)",
    )

    def _tmfc037_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        for rec in self:
            payload = _loads(rec.payload_json) or {}
            items = payload.get("relatedParty") if isinstance(payload, dict) else payload
            party_refs, role_refs = _collect(items or [])
            updates = {}
            if party_refs:
                p = Partner.search([("tmf_id", "in", party_refs)])
                if p:
                    updates["tmfc037_related_partner_ids"] = [(6, 0, p.ids)]
            if role_refs:
                r = PartyRole.search([("tmf_id", "in", role_refs)])
                if r:
                    updates["tmfc037_party_role_ids"] = [(6, 0, r.ids)]

            def _refs_of(*keys):
                refs = []
                if not isinstance(payload, dict):
                    return refs
                for key in keys:
                    value = payload.get(key)
                    if isinstance(value, dict):
                        refs.append(value)
                    elif isinstance(value, list):
                        refs.extend(v for v in value if isinstance(v, dict))
                return [str(r.get("id")).strip() for r in refs if r.get("id")]

            def _rebuild(field_name, model, ids):
                if not ids:
                    return
                found = self.env[model].sudo().search([("tmf_id", "in", ids)])
                if found and set(found.ids) != set(rec[field_name].ids):
                    updates[field_name] = [(6, 0, found.ids)]

            _rebuild("tmfc037_service_ids", "tmf.service",
                     _refs_of("service", "serviceRef", "monitoredService"))
            _rebuild("tmfc037_resource_ids", "stock.lot",
                     _refs_of("resource", "resourceRef", "monitoredResource"))
            _rebuild("tmfc037_slo_ids", "tmf.service.level.objective",
                     _refs_of("serviceLevelObjective"))
            _rebuild("tmfc037_sls_ids", "tmf.service.level.specification",
                     _refs_of("serviceLevelSpecification"))

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc037_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and "payload_json" in vals:
            try:
                self._tmfc037_resolve_refs()
            except Exception:
                pass
        return res


class TMFC037WiringTools(models.AbstractModel):
    _name = "tmfc037.wiring.tools"
    _description = "TMFC037 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        Rec = self.env["tmf.performance.management.resource"].sudo()
        Rec.search([])._tmfc037_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_service_catalog_event(self, payload):
        """TMF633 serviceSpecification change events: re-resolve refs."""
        return self._handle_party_event(payload)

    @api.model
    def _handle_service_inventory_event(self, payload):
        """TMF638 service C/AVC/state/D events: re-resolve monitored services."""
        return self._handle_party_event(payload)

    @api.model
    def _handle_resource_inventory_event(self, payload):
        """TMF639 resource C/AVC/state/D events: re-resolve monitored resources."""
        return self._handle_party_event(payload)

    @api.model
    def _handle_process_flow_event(self, payload):
        """TMF701 flow events: sync local flow state by tmf_id."""
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
