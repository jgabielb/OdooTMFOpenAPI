# -*- coding: utf-8 -*-
"""TMFC030 BillGeneration wiring tools."""

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


class TMFC030WiringTools(models.AbstractModel):
    _name = "tmfc030.wiring.tools"
    _description = "TMFC030 Wiring Tools - Bill Generation wiring"

    def _refresh(self, json_field, ref_id):
        bills = self.env["tmf.customer.bill"].sudo().search([(json_field, "ilike", ref_id)])
        if bills:
            bills._tmfc030_resolve_refs()

    @api.model
    def _handle_billing_account_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if ref_id:
                self._refresh("tmfc030_billing_account_json", ref_id)
        except Exception:
            pass
        return True

    @api.model
    def _handle_party_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if ref_id:
                self._refresh("tmfc030_related_party_json", ref_id)
        except Exception:
            pass
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)
