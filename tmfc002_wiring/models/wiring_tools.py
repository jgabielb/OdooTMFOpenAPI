# -*- coding: utf-8 -*-
"""TMFC002 subscribed-event reconciliation tools.

YAML subscribed events: TMF679 POQ stateChange, TMF673 geographicAddressValidation
stateChange, TMF676 payment create/stateChange, TMF716 resourceReservation events.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class TMFC002WiringTools(models.AbstractModel):
    _name = "tmfc002.wiring.tools"
    _description = "TMFC002 Wiring Reconciliation Tools"

    def _extract_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        event = payload.get("event")
        if isinstance(event, dict):
            if isinstance(event.get("resource"), dict):
                return event["resource"]
            for value in event.values():
                if isinstance(value, dict) and value.get("id"):
                    return value
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    def _apply_state(self, model_name, resource, state_field="state"):
        """Update the local record's state from the event resource, if it exists."""
        ref_id = str((resource or {}).get("id") or "").strip()
        state = (resource or {}).get(state_field) or (resource or {}).get("status")
        if not ref_id or not state:
            return self.env[model_name].sudo().browse()
        rec = self.env[model_name].sudo().search([("tmf_id", "=", ref_id)], limit=1)
        if rec:
            try:
                rec.with_context(skip_tmf_wiring=True).write({state_field: state})
            except Exception:
                # foreign state value outside the local selection — keep local state
                _logger.info("TMFC002: state %r not applicable to %s %s",
                             state, model_name, ref_id)
        return rec

    def handle_poq_event(self, payload):
        """TMF679 POQ stateChange: reconcile local POQ state, refresh quote/order links."""
        resource = self._extract_resource(payload)
        rec = self._apply_state("tmf.check.product.offering.qualification", resource)
        if not rec:
            self._apply_state("tmf.query.product.offering.qualification", resource)
        if rec:
            quotes = self.env["tmf.quote"].sudo().search(
                [("tmfc002_poq_ids", "in", rec.ids)])
            quotes._tmfc002_resolve_refs(changed_keys={"poq_json"})

    def handle_address_validation_event(self, payload):
        """TMF673 geographicAddressValidation stateChange: reconcile local state."""
        self._apply_state("tmf.geographic.address.validation",
                          self._extract_resource(payload))

    def handle_payment_event(self, payload):
        """TMF676 payment create/stateChange: reconcile local payment status."""
        self._apply_state("tmf.payment", self._extract_resource(payload),
                          state_field="status")

    def handle_reservation_event(self, payload):
        """TMF716 resourceReservation lifecycle: reconcile local reservation state."""
        resource = self._extract_resource(payload)
        rec = self._apply_state("tmf.resource.reservation", resource)
        if not rec:
            self._apply_state("tmf.cancel.resource.reservation", resource)
