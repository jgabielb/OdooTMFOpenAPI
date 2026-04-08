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

        return res


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
        _logger.debug("TMFC007 payload for %s/%s: %s", source, event_name, json.dumps(payload))

    # ------------------------------------------------------------------
    # TMF652 ResourceOrder events
    # ------------------------------------------------------------------

    def handle_resource_order_event(self, event_name, payload):
        if event_name not in TMFC007_RESOURCE_ORDER_EVENTS:
            return
        self._log_received_event("resourceOrder", event_name, payload)

    # ------------------------------------------------------------------
    # TMF645 ServiceQualification events
    # ------------------------------------------------------------------

    def handle_service_qualification_event(self, event_name, payload):
        if event_name not in TMFC007_SERVICE_QUALIFICATION_EVENTS:
            return
        self._log_received_event("serviceQualification", event_name, payload)

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


