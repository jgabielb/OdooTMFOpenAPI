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

    def _extract_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        ev = payload.get("event")
        if isinstance(ev, dict):
            if isinstance(ev.get("resource"), dict):
                return ev["resource"]
            for value in ev.values():
                if isinstance(value, dict) and value.get("id"):
                    return value
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    def _sync_states_and_link(self, model_name, resource, id_field="tmf_id",
                              link_field=None):
        """Sync administrative/operational/usage state and link to referencing orders."""
        ref_id = str((resource or {}).get("id") or "").strip()
        if not ref_id:
            return
        rec = self.env[model_name].sudo().search([(id_field, "=", ref_id)], limit=1)
        if rec:
            vals = {}
            for src, dst in (("administrativeState", "administrative_state"),
                             ("operationalState", "operational_state"),
                             ("usageState", "usage_state"),
                             ("state", "state")):
                if resource.get(src) and dst in rec._fields:
                    vals[dst] = resource[src]
            if vals:
                try:
                    rec.with_context(skip_tmf_wiring=True).write(vals)
                except Exception:
                    pass
        # link to resource orders referenced in the event payload
        if rec and link_field:
            order_refs = resource.get("resourceOrder") or []
            if isinstance(order_refs, dict):
                order_refs = [order_refs]
            order_ids = [str((o or {}).get("id") or "").strip()
                         for o in order_refs if isinstance(o, dict)]
            order_ids = [o for o in order_ids if o]
            if order_ids:
                orders = self.env["tmf.resource.order"].sudo().search(
                    [("tmf_id", "in", order_ids)])
                for order in orders:
                    if rec.id not in order[link_field].ids:
                        order.with_context(skip_tmf_wiring=True).write(
                            {link_field: [(4, rec.id)]})

    @api.model
    def _handle_resource_function_event(self, payload):
        """TMF664 resourceFunction / monitor / heal / scale / migrate events."""
        try:
            self._sync_states_and_link(
                "tmf.resource.function", self._extract_resource(payload),
                link_field="tmfc011_resource_function_ids")
        except Exception:
            pass
        return True

    @api.model
    def _handle_activation_resource_event(self, payload):
        """TMF702 resource change / monitor events."""
        try:
            resource = self._extract_resource(payload)
            self._sync_states_and_link(
                "tmf702.resource", resource,
                link_field="tmfc011_activation_resource_ids")
            # monitor events reference the tmf702.monitor resource instead
            self._sync_states_and_link("tmf702.monitor", resource,
                                       id_field="tmf702_id")
        except Exception:
            pass
        return True
