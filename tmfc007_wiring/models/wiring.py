import json
import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


# Event-type constants derived from TMFC007 YAML
TMFC007_RESOURCE_ORDER_EVENTS = {
    "ResourceOrderStateChangeEvent",
    "ResourceOrderAttributeValueChangeEvent",
    "ResourceOrderInformationRequiredEvent",
    "CancelResourceOrderStateChangeEvent",
    "CancelResourceOrderInformationRequiredEvent",
}

TMFC007_SERVICE_QUALIFICATION_EVENTS = {
    "CheckServiceQualificationStateChangeEvent",
    "QueryServiceQualificationStateChangeEvent",
}

TMFC007_COMMUNICATION_EVENTS = {
    "CommunicationMessageStateChangeEvent",
}

TMFC007_WORK_ORDER_EVENTS = {
    "WorkOrderStateChangeEvent",
}


class TMFC007ServiceOrderWiring(models.Model):
    """TMFC007 wiring extension for tmf.service.order.

    First-pass responsibilities (kept deliberately narrow and additive):

    - Preserve existing TMF641 behaviour (create/update/delete events).
    - Add state-change event publication when the ServiceOrder ``state``
      field changes.
    - Emit cancelServiceOrder state-change events when a cancellation
      date is first set.
    - Introduce optional links to TMF701 process flows without creating
      or mutating flows yet (linkage only).

    This model must not change existing TMF API URLs or payload shapes.
    """

    _inherit = "tmf.service.order"

    # ------------------------------------------------------------------
    # TMF701 linkage (shared with other TMFCs)
    # ------------------------------------------------------------------

    process_flow_ids = fields.Many2many(
        "tmf.process.flow",
        "tmfc007_service_order_process_flow_rel",
        "service_order_id",
        "process_flow_id",
        string="Process Flows (TMF701)",
        help=(
            "Optional linkage to TMF701 processFlow records that track "
            "the lifecycle of this ServiceOrder. Provisioning of flows "
            "remains the responsibility of orchestration components."
        ),
    )

    task_flow_ids = fields.Many2many(
        "tmf.task.flow",
        "tmfc007_service_order_task_flow_rel",
        "service_order_id",
        "task_flow_id",
        string="Task Flows (TMF701)",
        help=(
            "Optional linkage to TMF701 taskFlow records spawned as part "
            "of ServiceOrder fulfilment."
        ),
    )

    # ------------------------------------------------------------------
    # TMF638 ServiceInventory dependency wiring
    # ------------------------------------------------------------------

    service_ref_json = fields.Json(
        default=list,
        string="Service refs JSON (TMF638)",
        help=(
            "Raw TMF638 Service references extracted from serviceOrderItem.service "
            "payloads. Kept for CTK-level fidelity; relational links below are the "
            "authoritative navigation surface inside Odoo."
        ),
    )

    service_ids = fields.Many2many(
        "tmf.service",
        "tmfc007_service_order_service_rel",
        "service_order_id",
        "service_id",
        string="Services (TMF638)",
        help=(
            "Resolved TMF638 Service records referenced from serviceOrderItem.service. "
            "Resolution is best-effort and never alters TMF641 payloads or URLs."
        ),
    )

    def _tmfc007_notify_state_transitions(self, old_state_map, old_cancel_map):
        """Publish TMF641 state-change and cancelServiceOrder events.

        This is called *after* the core create/write has executed so that
        ``to_tmf_json()`` reflects the latest persisted state. It relies on
        snapshots captured before the write to detect transitions.
        """

        hub = self.env["tmf.hub.subscription"].sudo()

        for rec in self:
            try:
                payload = rec.to_tmf_json()
            except Exception as exc:  # pragma: no cover - defensive
                _logger.exception("TMFC007: to_tmf_json failed during state notify: %s", exc)
                continue

            previous_state = old_state_map.get(rec.id)
            current_state = rec.state
            if previous_state != current_state and current_state:
                try:
                    hub._notify_subscribers(
                        "serviceOrder",
                        "ServiceOrderStateChangeEvent",
                        payload,
                    )
                except Exception as exc:  # pragma: no cover - best-effort
                    _logger.exception(
                        "TMFC007: error notifying ServiceOrderStateChangeEvent for %s: %s",
                        rec.id,
                        exc,
                    )

            # Cancellation state-change: detect first non-empty cancellationDate
            prev_cancel = old_cancel_map.get(rec.id)
            has_cancel = bool(rec.cancellation_date)
            if not prev_cancel and has_cancel:
                try:
                    hub._notify_subscribers(
                        "serviceOrder",
                        "CancelServiceOrderStateChangeEvent",
                        payload,
                    )
                except Exception as exc:  # pragma: no cover - best-effort
                    _logger.exception(
                        "TMFC007: error notifying CancelServiceOrderStateChangeEvent for %s: %s",
                        rec.id,
                        exc,
                    )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        # No special state handling on initial create: the core model already
        # emits ServiceOrderCreateEvent and AttributeValueChangeEvent.

        # Best-effort dependency resolution (kept additive and idempotent).
        try:
            recs._tmfc007_resolve_tmf_refs()
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC007: TMF638 ref resolution on create failed: %s", exc)

        return recs

    def write(self, vals):
        # Capture pre-write snapshots for transition detection.
        old_state_map = {rec.id: rec.state for rec in self}
        old_cancel_map = {rec.id: bool(rec.cancellation_date) for rec in self}

        res = super().write(vals)

        # After the underlying write (and its existing _notify calls),
        # publish state-change events as an additive behaviour.
        try:
            self._tmfc007_notify_state_transitions(old_state_map, old_cancel_map)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC007: state transition notification failed: %s", exc)

        # Refresh TMF638 dependency wiring when relevant payload fields change.
        if any(k in vals for k in ("service_order_item",)):
            try:
                self._tmfc007_resolve_tmf_refs()
            except Exception as exc:  # pragma: no cover - defensive
                _logger.exception("TMFC007: TMF638 ref resolution on write failed: %s", exc)

        return res

    # ------------------------------------------------------------------
    # Dependency resolution helpers (TMF638)
    # ------------------------------------------------------------------

    def _tmfc007_resolve_tmf_refs(self):
        """Resolve TMF638 Service references from serviceOrderItem.

        Evidence-backed mapping (from TMF641/TMF638):
        - serviceOrderItem[*].service → ServiceRefOrValue (id, href, name,…)

        We treat serviceOrderItem as the single source of truth and:
        - store the raw list of service refs in ``service_ref_json``;
        - resolve ``service_ids`` by looking up ``tmf.service`` by ``tmf_id``
          (falling back to numeric record IDs when appropriate).

        This method never mutates the underlying TMF641 JSON fields or URLs
        and is safe to call repeatedly (idempotent).
        """

        Service = self.env["tmf.service"].sudo()
        ctx = {"skip_tmf_wiring": True}

        for rec in self:
            items = rec.service_order_item or []
            if isinstance(items, dict):
                items = [items]

            service_refs = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                svc = item.get("service") or {}
                if isinstance(svc, dict) and (svc.get("id") or svc.get("href")):
                    service_refs.append(svc)

            # Persist raw refs for traceability
            updates = {"service_ref_json": service_refs}

            # Resolve relational links
            ref_ids = []
            for ref in service_refs:
                sid = str(ref.get("id") or "").strip()
                if not sid:
                    continue
                ref_ids.append(sid)

            resolved_ids = []
            if ref_ids:
                # Primary: tmf_id lookup
                resolved_ids = Service.search([("tmf_id", "in", ref_ids)]).ids
                # Fallback: direct record IDs when numeric
                missing = {rid for rid in ref_ids if rid not in {str(s.tmf_id) for s in Service.browse(resolved_ids)}}
                numeric_ids = [int(mid) for mid in missing if mid.isdigit()]
                if numeric_ids:
                    resolved_ids.extend(Service.browse(numeric_ids).ids)

            updates["service_ids"] = [(6, 0, resolved_ids)] if resolved_ids else [(5, 0, 0)]
            rec.with_context(**ctx).write(updates)


class TMFC007WiringTools(models.AbstractModel):
    """Thin wiring/tools layer for TMFC007 event listeners.

    In this first implementation pass we intentionally keep behaviour
    minimal and **non-mutating**: listener handlers validate envelopes and
    log receipt, but do not yet reconcile into local ServiceOrder state.

    This gives us:
    - stable, testable HTTP listener surfaces for TMF652/645/681/697;
    - a single place to grow reconciliation logic in future sprints;
    - zero behavioural impact on existing flows.
    """

    _name = "tmfc007.wiring.tools"
    _description = "TMFC007 wiring helpers"

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _log_received_event(self, source, event_name, payload):
        _logger.info("TMFC007: received %s event %s", source, event_name)
        # Keep logs compact to avoid noise; callers can enable debug logging
        # to inspect full payloads during integration.
        _logger.debug(
            "TMFC007 payload for %s/%s: %s",
            source,
            event_name,
            json.dumps(payload),
        )

    def _extract_event_resource(self, payload):
        """Extract nested resource dict from a TMF event envelope.

        Mirrors the helper used in TMFC003 so that TMFC007 can reuse
        the same reconciliation patterns where appropriate.
        """

        if not isinstance(payload, dict):
            return {}
        event = payload.get("event")
        if isinstance(event, dict):
            for key in ("resourceOrder", "serviceQualification", "communicationMessage", "workOrder"):
                if isinstance(event.get(key), dict):
                    return event[key]
        # Fallback: treat payload as the resource itself
        return payload

    def _extract_resource_id(self, payload):
        if not isinstance(payload, dict):
            return ""
        resource = self._extract_event_resource(payload)
        return str(resource.get("id") or payload.get("id") or "").strip()

    # ------------------------------------------------------------------
    # TMF652 ResourceOrder events
    # ------------------------------------------------------------------

    def handle_resource_order_event(self, event_name, payload):
        if event_name not in TMFC007_RESOURCE_ORDER_EVENTS:
            return

        self._log_received_event("resourceOrder", event_name, payload)

        # Delegate core reconciliation to TMFC003 wiring tools when present,
        # so that state aggregation between ResourceOrder → ServiceOrder →
        # ProductOrder stays consistent across TMFCs.
        try:
            tools = self.env["tmfc003.wiring.tools"].sudo()
        except Exception:  # pragma: no cover - defensive
            tools = None

        if tools and hasattr(tools, "handle_resource_order_event"):
            try:
                tools.handle_resource_order_event(event_name, payload)
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception(
                    "TMFC007: delegation to TMFC003 for ResourceOrder event %s failed: %s",
                    event_name,
                    exc,
                )

    # ------------------------------------------------------------------
    # TMF645 ServiceQualification events
    # ------------------------------------------------------------------

    def handle_service_qualification_event(self, event_name, payload):
        if event_name not in TMFC007_SERVICE_QUALIFICATION_EVENTS:
            return
        self._log_received_event("serviceQualification", event_name, payload)

        # Minimal, safe reconciliation: update local ServiceQualification
        # state when the referenced record exists. We deliberately avoid
        # mutating ServiceOrders here; TMFC027 owns deeper POQ/SQ logic.
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        sq = (
            self.env["tmf.service.qualification"].sudo().search([
                ("tmf_id", "=", ref_id),
            ], limit=1)
        )
        if not sq:
            return

        resource = self._extract_event_resource(payload)
        new_state = str(resource.get("state") or "").strip()
        if not new_state or new_state == (sq.state or ""):
            return

        try:
            sq.with_context(skip_tmf_wiring=True).write({"state": new_state})
        except Exception as exc:  # pragma: no cover - best-effort
            _logger.exception("TMFC007: failed to update ServiceQualification %s state: %s", ref_id, exc)

    # ------------------------------------------------------------------
    # TMF681 Communication events
    # ------------------------------------------------------------------

    def handle_communication_event(self, event_name, payload):
        if event_name not in TMFC007_COMMUNICATION_EVENTS:
            return
        self._log_received_event("communication", event_name, payload)

    # ------------------------------------------------------------------
    # TMF697 WorkOrder events
    # ------------------------------------------------------------------

    def handle_work_order_event(self, event_name, payload):
        if event_name not in TMFC007_WORK_ORDER_EVENTS:
            return
        self._log_received_event("workOrder", event_name, payload)

