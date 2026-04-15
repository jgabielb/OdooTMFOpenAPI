# -*- coding: utf-8 -*-
"""TMFC011 ResourceOrderManagement wiring tools.

Handles TMF632 Party / TMF669 PartyRole / TMF634 ResourceSpecification
subscribed events and conservatively refreshes affected resource orders.
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


class TMFC011WiringTools(models.AbstractModel):
    _name = "tmfc011.wiring.tools"
    _description = "TMFC011 Wiring Tools - Resource Order wiring"

    @api.model
    def _handle_party_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if not ref_id:
                return True
            orders = self.env["tmf.resource.order"].sudo().search(
                [("tmfc011_related_party_json", "ilike", ref_id)]
            )
            if orders:
                orders._tmfc011_resolve_refs()
        except Exception:
            pass
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_resource_spec_event(self, payload):
        try:
            ref_id = _extract_id(payload or {})
            if not ref_id:
                return True
            Order = self.env["tmf.resource.order"].sudo()
            orders = Order.search(
                [("tmfc011_resource_specification_ids.tmf_id", "=", ref_id)]
            )
            if orders:
                orders._tmfc011_resolve_refs()
        except Exception:
            pass
        return True
