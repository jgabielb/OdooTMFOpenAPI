# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


TMFC029_BILLING_ACCOUNT_EVENTS = {
    "BillingAccountCreateEvent",
    "BillingAccountAttributeValueChangeEvent",
    "BillingAccountStateChangeEvent",
    "BillingAccountDeleteEvent",
}

TMFC029_CUSTOMER_BILL_EVENTS = {
    "CustomerBillCreateEvent",
    "CustomerBillAttributeValueChangeEvent",
    "CustomerBillStateChangeEvent",
    "CustomerBillDeleteEvent",
}

TMFC029_PARTY_EVENTS = {
    "PartyCreateEvent",
    "PartyAttributeValueChangeEvent",
    "PartyStateChangeEvent",
    "PartyDeleteEvent",
}


class TMFC029WiringTools(models.AbstractModel):
    """TMFC029 listener helpers.

    All handlers are best-effort, idempotent, and never create master
    data: they only refresh the side-car relational links on payments
    that already reference the affected id.
    """

    _name = "tmfc029.wiring.tools"
    _description = "TMFC029 wiring helpers"

    def _log(self, source, event_name, payload):
        _logger.info("TMFC029: received %s event %s", source, event_name)
        _logger.debug("TMFC029 payload for %s/%s: %s", source, event_name, json.dumps(payload))

    def _extract_resource(self, payload, preferred_keys=None):
        if not isinstance(payload, dict):
            return {}
        event = payload.get("event")
        if isinstance(event, dict):
            for key in (preferred_keys or []):
                if isinstance(event.get(key), dict):
                    return event[key]
            if isinstance(event.get("resource"), dict):
                return event["resource"]
        return payload

    def _extract_id(self, payload, preferred_keys=None):
        resource = self._extract_resource(payload, preferred_keys)
        return str((resource or {}).get("id") or payload.get("id") or "").strip()

    @api.model
    def handle_billing_account_event(self, event_name, payload):
        if event_name not in TMFC029_BILLING_ACCOUNT_EVENTS:
            return
        self._log("billingAccount", event_name, payload)
        ref_id = self._extract_id(payload, ["billingAccount"])
        if not ref_id:
            return
        Payment = self.env["tmf.payment"].sudo()
        affected = Payment.search([("account_json", "ilike", ref_id)])
        if affected:
            try:
                affected._tmfc029_resolve_refs()
            except Exception as exc:  # pragma: no cover
                _logger.exception("TMFC029: billingAccount reconcile failed: %s", exc)

    @api.model
    def handle_customer_bill_event(self, event_name, payload):
        if event_name not in TMFC029_CUSTOMER_BILL_EVENTS:
            return
        self._log("customerBill", event_name, payload)
        ref_id = self._extract_id(payload, ["customerBill"])
        if not ref_id:
            return
        Payment = self.env["tmf.payment"].sudo()
        affected = Payment.search([("payment_item_json", "ilike", ref_id)])
        if affected:
            try:
                affected._tmfc029_resolve_refs()
            except Exception as exc:  # pragma: no cover
                _logger.exception("TMFC029: customerBill reconcile failed: %s", exc)

    @api.model
    def handle_party_event(self, event_name, payload):
        if event_name not in TMFC029_PARTY_EVENTS:
            return
        self._log("party", event_name, payload)
        ref_id = self._extract_id(payload, ["party", "individual", "organization"])
        if not ref_id:
            return
        Payment = self.env["tmf.payment"].sudo()
        affected = Payment.search([("account_json", "ilike", ref_id)])
        if affected:
            try:
                affected._tmfc029_resolve_refs()
            except Exception as exc:  # pragma: no cover
                _logger.exception("TMFC029: party reconcile failed: %s", exc)
