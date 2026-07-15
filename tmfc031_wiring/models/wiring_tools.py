# -*- coding: utf-8 -*-
"""TMFC031 subscribed-event reconciliation (TMF635 usage / usageSpecification)."""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class TMFC031WiringTools(models.AbstractModel):
    _name = "tmfc031.wiring.tools"
    _description = "TMFC031 Wiring Reconciliation Tools"

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

    def handle_usage_event(self, payload):
        """TMF635 usage events: re-resolve or prune bill/rate usage links."""
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if not ref_id:
            return
        usage = self.env["tmf.usage"].sudo().search([("tmf_id", "=", ref_id)], limit=1)
        Bill = self.env["tmf.customer.bill"].sudo().with_context(active_test=False)
        if usage:
            # keep local state in sync where the payload carries one
            state = (resource or {}).get("status") or (resource or {}).get("state")
            if state and "status" in usage._fields:
                try:
                    usage.with_context(skip_tmf_wiring=True).write({"status": state})
                except Exception:
                    pass
            bills = Bill.search([("usage_json", "!=", False)])
            bills._resolve_tmf_refs(changed_keys={"usage_json"})
            return
        # usage deleted upstream: prune json + relational links
        bills = Bill.search([("usage_ids.tmf_id", "=", ref_id)])
        bills |= Bill.search([("usage_json", "!=", False)]).filtered(
            lambda b: any(isinstance(i, dict)
                          and str(i.get("id") or "").strip() == ref_id
                          for i in (b.usage_json or [])))
        for bill in bills:
            json_refs = [i for i in (bill.usage_json or [])
                         if str((i or {}).get("id") or "").strip() != ref_id]
            kept = bill.usage_ids.filtered(lambda u: (u.tmf_id or str(u.id)) != ref_id)
            bill.with_context(skip_tmf_wiring=True).write({
                "usage_ids": [(6, 0, kept.ids)],
                "usage_json": json_refs,
            })

    def handle_usage_specification_event(self, payload):
        """TMF635 usageSpecification events: sync local specification state."""
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if not ref_id:
            return
        spec = self.env["tmf.usage.specification"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1)
        if not spec:
            return
        vals = {}
        for src, dst in (("name", "name"), ("description", "description")):
            if resource.get(src) and dst in spec._fields:
                vals[dst] = resource[src]
        if vals:
            try:
                spec.with_context(skip_tmf_wiring=True).write(vals)
            except Exception:
                _logger.info("TMFC031: usageSpecification %s reconcile skipped", ref_id)
