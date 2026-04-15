# -*- coding: utf-8 -*-
"""TMFC012 ResourceInventory wiring tools.

Conservatively refreshes stock.lot records that already reference a
changed upstream TMF entity. Never creates master data; never raises.
"""

from odoo import api, models


def _extract_id(payload):
    if not isinstance(payload, dict):
        return ""
    ev = payload.get("event")
    if isinstance(ev, dict) and isinstance(ev.get("resource"), dict):
        return str(ev["resource"].get("id") or "").strip()
    if isinstance(payload.get("resource"), dict):
        return str(payload["resource"].get("id") or "").strip()
    return str(payload.get("id") or "").strip()


class TMFC012WiringTools(models.AbstractModel):
    _name = "tmfc012.wiring.tools"
    _description = "TMFC012 Wiring Tools - Resource Inventory wiring"

    def _refresh(self, json_field, ref_id):
        lots = self.env["stock.lot"].sudo().search([(json_field, "ilike", ref_id)])
        if lots:
            lots._tmfc012_resolve_refs()

    @api.model
    def _handle_resource_spec_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if ref_id:
                self._refresh("tmfc012_resource_spec_ref_json", ref_id)
        except Exception:
            pass
        return True

    @api.model
    def _handle_party_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if ref_id:
                self._refresh("tmfc012_related_party_json", ref_id)
        except Exception:
            pass
        return True

    @api.model
    def _handle_place_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if ref_id:
                self._refresh("tmfc012_place_ref_json", ref_id)
        except Exception:
            pass
        return True
