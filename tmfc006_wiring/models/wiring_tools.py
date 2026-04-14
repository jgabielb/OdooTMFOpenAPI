# -*- coding: utf-8 -*-
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


def _resolve_ids(env, model, items, id_field="tmf_id"):
    """Batch-search model by tmf_id for all item dicts. Returns list of record IDs.

    This mirrors the helper used in other TMFC wiring addons (TMFC001/TMFC005/TMFC027)
    so TMFC006 stays consistent with the broader wiring pattern.
    """
    ref_ids = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("id") or "").strip()
        if ref_id:
            ref_ids.append(ref_id)
    if not ref_ids:
        return []
    return env[model].sudo().search([(id_field, "in", ref_ids)]).ids


def _extract_event_resource(payload):
    """Extract the TMF resource from an event envelope.

    Accepts both CTK-style `{event: {resource: {...}}}` and simpler payloads
    where the resource is at the top level. This is intentionally tolerant so
    TMFC006 listeners can accept slightly different shapes without failing.
    """
    if not isinstance(payload, dict):
        return {}
    event = payload.get("event")
    if isinstance(event, dict) and isinstance(event.get("resource"), dict):
        return event["resource"]
    if isinstance(payload.get("resource"), dict):
        return payload["resource"]
    return payload


def _extract_resource_id(payload):
    resource = _extract_event_resource(payload)
    ref_id = str(resource.get("id") or payload.get("id") or "").strip()
    return ref_id


class TMFC006WiringTools(models.AbstractModel):
    _name = "tmfc006.wiring.tools"
    _description = "TMFC006 Wiring Tools - Service Catalog foundational wiring"

    # NOTE: TMFC006 side-car fields now live on ``tmf.service.specification``
    # via ``tmfc006_wiring/models/service_specification.py``. This AbstractModel
    # only hosts the reconciliation helpers.

    @api.model
    def _resolve_service_spec_references(self, specs=None):
        """Best-effort resolution helper for TMF633 ServiceSpecification refs.

        Behaviour (pass 2):
        - expects `id`/`tmf_id` fields in incoming payload fragments,
        - **never** creates TMF master-data records, only links to existing ones,
        - can be safely called from controllers/models via `skip_tmf_wiring` context.

        When `specs` is falsy we default to all `tmf.service.specification` records
        that carry TMFC006 JSON reference fields.
        """
        ServiceSpec = self.env["tmf.service.specification"].sudo()

        if not specs:
            specs = ServiceSpec.search([
                "|",
                ("service_spec_related_party_json", "!=", False),
                "|",
                ("service_spec_resource_spec_json", "!=", False),
                ("service_spec_entity_spec_json", "!=", False),
            ])
        elif not isinstance(specs, ServiceSpec.__class__):
            # Accept a recordset or a single record; ignore anything else.
            try:
                specs = ServiceSpec.browse(getattr(specs, "ids", []))
            except Exception:
                specs = ServiceSpec.browse([])

        ctx = {"skip_tmf_wiring": True}
        for spec in specs:
            updates = {}

            # Effective JSON sources: prefer dedicated TMFC006 fields, but fall back
            # to baseline TMF633 JSON if side-car fields are still empty.
            related_party_json = _loads(spec.service_spec_related_party_json) or _loads(spec.related_party) or []
            resource_spec_json = _loads(spec.service_spec_resource_spec_json) or []
            entity_spec_json = _loads(spec.service_spec_entity_spec_json) or []

            # TMF632 relatedParty -> res.partner (excluding PartyRole entries)
            if not spec.related_partner_ids and related_party_json:
                items = [
                    i
                    for i in (related_party_json or [])
                    if isinstance(i, dict)
                    and i.get("@type") not in ("PartyRole", "PartyRoleRef")
                ]
                ids = _resolve_ids(self.env, "res.partner", items)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            # TMF669 relatedParty[PartyRole] -> tmf.party.role
            if not spec.party_role_ids and related_party_json:
                items = [
                    i
                    for i in (related_party_json or [])
                    if isinstance(i, dict)
                    and i.get("@type") in ("PartyRole", "PartyRoleRef")
                ]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["party_role_ids"] = [(6, 0, ids)]

            # TMF634 resourceSpecification -> tmf.resource.specification
            if not spec.resource_specification_ids and resource_spec_json:
                ids = _resolve_ids(self.env, "tmf.resource.specification", resource_spec_json)
                if ids:
                    updates["resource_specification_ids"] = [(6, 0, ids)]

            # TMF662 entitySpecification/associationSpecification -> tmf.entity.specification
            if not spec.entity_specification_ids and entity_spec_json:
                ids = _resolve_ids(self.env, "tmf.entity.specification", entity_spec_json)
                if ids:
                    updates["entity_specification_ids"] = [(6, 0, ids)]

            if updates:
                spec.with_context(**ctx).write(updates)

        return True

    @api.model
    def _handle_resource_catalog_event(self, payload):
        """Entry point for TMF634 callbacks.

        Pass 2 behaviour (conservative):
        - on create/change events, re-run reference resolution for any service
          specifications that reference the affected ResourceSpecification;
        - on delete events, drop JSON + relational links to the missing
          ResourceSpecification without touching other data.
        """
        try:
            ref_id = _extract_resource_id(payload or {})
            if not ref_id:
                return True

            ResourceSpec = self.env["tmf.resource.specification"].sudo()
            ServiceSpec = self.env["tmf.service.specification"].sudo()

            spec = ResourceSpec.search([("tmf_id", "=", ref_id)], limit=1)

            # Service specifications that currently reference this resource spec
            svc_specs = ServiceSpec.search([
                "|",
                ("service_spec_resource_spec_json", "ilike", ref_id),
                ("resource_specification_ids.tmf_id", "=", ref_id),
            ])

            if spec:
                # ResourceSpecification still exists: refresh TMF wiring for all
                # affected ServiceSpecifications.
                self._resolve_service_spec_references(svc_specs)
                return True

            # ResourceSpecification no longer exists: strip links on
            # ServiceSpecifications while preserving other references.
            for svc in svc_specs:
                kept_rel = svc.resource_specification_ids.filtered(
                    lambda r: (r.tmf_id or str(r.id)) != ref_id
                )
                json_refs = [
                    item
                    for item in (_loads(svc.service_spec_resource_spec_json) or [])
                    if str((item or {}).get("id") or "").strip() != ref_id
                ]
                svc.with_context(skip_tmf_wiring=True).write({
                    "resource_specification_ids": [(6, 0, kept_rel.ids)],
                    "service_spec_resource_spec_json": json_refs,
                })

            return True
        except Exception:
            # Never let TMFC006 listeners break the hub pipeline.
            return True

    @api.model
    def _handle_entity_catalog_event(self, payload):
        """Entry point for TMF662 callbacks.

        Similar to `_handle_resource_catalog_event`, this reconciles
        EntitySpecification links in a best-effort, non-throwing way.
        """
        try:
            ref_id = _extract_resource_id(payload or {})
            if not ref_id:
                return True

            EntitySpec = self.env["tmf.entity.specification"].sudo()
            ServiceSpec = self.env["tmf.service.specification"].sudo()

            spec = EntitySpec.search([("tmf_id", "=", ref_id)], limit=1)

            svc_specs = ServiceSpec.search([
                "|",
                ("service_spec_entity_spec_json", "ilike", ref_id),
                ("entity_specification_ids.tmf_id", "=", ref_id),
            ])

            if spec:
                self._resolve_service_spec_references(svc_specs)
                return True

            for svc in svc_specs:
                kept_rel = svc.entity_specification_ids.filtered(
                    lambda r: (r.tmf_id or str(r.id)) != ref_id
                )
                json_refs = [
                    item
                    for item in (_loads(svc.service_spec_entity_spec_json) or [])
                    if str((item or {}).get("id") or "").strip() != ref_id
                ]
                svc.with_context(skip_tmf_wiring=True).write({
                    "entity_specification_ids": [(6, 0, kept_rel.ids)],
                    "service_spec_entity_spec_json": json_refs,
                })

            return True
        except Exception:
            return True
