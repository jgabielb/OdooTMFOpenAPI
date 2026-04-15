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

TMFC007_PARTY_EVENTS = {
    "PartyCreateEvent",
    "PartyAttributeValueChangeEvent",
    "PartyStateChangeEvent",
    "PartyDeleteEvent",
}

TMFC007_PARTY_ROLE_EVENTS = {
    "PartyRoleCreateEvent",
    "PartyRoleAttributeValueChangeEvent",
    "PartyRoleStateChangeEvent",
    "PartyRoleDeleteEvent",
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

    # ------------------------------------------------------------------
    # TMF632 Party / TMF669 PartyRole dependency wiring
    # ------------------------------------------------------------------

    tmfc007_related_partner_ids = fields.Many2many(
        "res.partner",
        "tmfc007_service_order_partner_rel",
        "service_order_id",
        "partner_id",
        string="Related Partners (TMF632)",
        help=(
            "Resolved TMF632 Party references from relatedParty. Additive to "
            "the base partner_id (which is the primary customer); this is the "
            "full set of related parties for TMFC007 navigation."
        ),
    )

    tmfc007_party_role_ids = fields.Many2many(
        "tmf.party.role",
        "tmfc007_service_order_party_role_rel",
        "service_order_id",
        "party_role_id",
        string="Party Roles (TMF669)",
        help=(
            "Resolved TMF669 PartyRole entries found inside relatedParty "
            "(items with @type PartyRole/PartyRoleRef)."
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

        try:
            recs._tmfc007_resolve_party_refs()
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC007: Party/PartyRole resolution on create failed: %s", exc)

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

        # Refresh TMF632/TMF669 wiring when relatedParty changes.
        if "related_party" in vals:
            try:
                self._tmfc007_resolve_party_refs()
            except Exception as exc:  # pragma: no cover - defensive
                _logger.exception("TMFC007: Party/PartyRole resolution on write failed: %s", exc)

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

    def _tmfc007_resolve_party_refs(self):
        """Resolve TMF632 Party / TMF669 PartyRole refs from related_party.

        Idempotent and additive: never alters base ``partner_id`` or
        ``related_party`` JSON. Splits relatedParty entries by ``@type``
        and resolves them into ``tmfc007_related_partner_ids`` and
        ``tmfc007_party_role_ids``.
        """

        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        ctx = {"skip_tmf_wiring": True}

        for rec in self:
            items = rec.related_party or []
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list):
                items = []

            partner_refs = []
            party_role_refs = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                kind = (item.get("@type") or "").strip()
                if kind in ("PartyRole", "PartyRoleRef"):
                    party_role_refs.append(item)
                else:
                    partner_refs.append(item)

            partner_ids = []
            for ref in partner_refs:
                rid = str(ref.get("id") or "").strip()
                if not rid:
                    continue
                hit = Partner.search([("tmf_id", "=", rid)], limit=1)
                if not hit and rid.isdigit():
                    hit = Partner.browse(int(rid))
                    if not hit.exists():
                        hit = Partner.browse([])
                if hit:
                    partner_ids.append(hit.id)

            role_ids = []
            for ref in party_role_refs:
                rid = str(ref.get("id") or "").strip()
                if not rid:
                    continue
                hit = PartyRole.search([("tmf_id", "=", rid)], limit=1)
                if not hit and rid.isdigit():
                    hit = PartyRole.browse(int(rid))
                    if not hit.exists():
                        hit = PartyRole.browse([])
                if hit:
                    role_ids.append(hit.id)

            updates = {
                "tmfc007_related_partner_ids": [(6, 0, partner_ids)] if partner_ids else [(5, 0, 0)],
                "tmfc007_party_role_ids": [(6, 0, role_ids)] if role_ids else [(5, 0, 0)],
            }
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

        # Safe, additive reconciliation:
        # - update local CommunicationMessage ``state`` when record exists;
        # - attach ServiceOrder links when the event payload carries
        #   ``serviceOrder`` references.

        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        Communication = self.env["tmf.communication.message"].sudo()
        msg = Communication.search([("tmf_id", "=", ref_id)], limit=1)
        if not msg:
            # Fallback: numeric database identifier
            if ref_id.isdigit():
                msg = Communication.browse(int(ref_id))
                if not msg.exists():
                    return
            else:
                return

        resource = self._extract_event_resource(payload)

        # 1) State reconciliation
        new_state = str(resource.get("state") or "").strip()
        if new_state and new_state != (msg.state or ""):
            try:
                msg.with_context(skip_tmf_wiring=True).write({"state": new_state})
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception(
                    "TMFC007: failed to update CommunicationMessage %s state: %s",
                    ref_id,
                    exc,
                )

        # 2) ServiceOrder dependency wiring (TMF641)
        svc_refs = resource.get("serviceOrder") or []
        if isinstance(svc_refs, dict):
            svc_refs = [svc_refs]
        if not isinstance(svc_refs, list):
            svc_refs = []

        service_ids = []
        service_ref_json = []
        if svc_refs:
            ServiceOrder = self.env["tmf.service.order"].sudo()
            for ref in svc_refs:
                if not isinstance(ref, dict):
                    continue
                sid = str(ref.get("id") or "").strip()
                if not sid:
                    continue
                service_ref_json.append(ref)
                so = ServiceOrder.search([("tmf_id", "=", sid)], limit=1)
                if not so and sid.isdigit():
                    so = ServiceOrder.browse(int(sid))
                if so and so.exists():
                    service_ids.append(so.id)

        if service_ids or service_ref_json:
            try:
                msg.with_context(skip_tmf_wiring=True).write(
                    {
                        "tmfc007_service_order_ref_json": service_ref_json,
                        "tmfc007_service_order_ids": [(6, 0, service_ids)],
                    }
                )
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception(
                    "TMFC007: failed to update CommunicationMessage %s service order links: %s",
                    ref_id,
                    exc,
                )

    # ------------------------------------------------------------------
    # TMF697 WorkOrder events
    # ------------------------------------------------------------------

    def handle_work_order_event(self, event_name, payload):
        if event_name not in TMFC007_WORK_ORDER_EVENTS:
            return
        self._log_received_event("workOrder", event_name, payload)

        # Safe, additive reconciliation for TMF713 Work records that are
        # acting as WorkOrders in the TMFC007 context:
        # - update ``state`` when the work record exists;
        # - wire any ServiceOrder references carried in the payload.

        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        Work = self.env["tmf.work"].sudo()
        work = Work.search([("tmf_id", "=", ref_id)], limit=1)
        if not work:
            if ref_id.isdigit():
                work = Work.browse(int(ref_id))
                if not work.exists():
                    return
            else:
                return

        resource = self._extract_event_resource(payload)

        # 1) State reconciliation
        new_state = str(resource.get("state") or "").strip()
        if new_state and new_state != (work.state or ""):
            try:
                work.with_context(skip_tmf_wiring=True).write({"state": new_state})
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception(
                    "TMFC007: failed to update Work %s state from WorkOrder event: %s",
                    ref_id,
                    exc,
                )

        # 2) ServiceOrder dependency wiring (TMF641)
        svc_refs = resource.get("serviceOrder") or []
        if isinstance(svc_refs, dict):
            svc_refs = [svc_refs]
        if not isinstance(svc_refs, list):
            svc_refs = []

        service_ids = []
        service_ref_json = []
        if svc_refs:
            ServiceOrder = self.env["tmf.service.order"].sudo()
            for ref in svc_refs:
                if not isinstance(ref, dict):
                    continue
                sid = str(ref.get("id") or "").strip()
                if not sid:
                    continue
                service_ref_json.append(ref)
                so = ServiceOrder.search([("tmf_id", "=", sid)], limit=1)
                if not so and sid.isdigit():
                    so = ServiceOrder.browse(int(sid))
                if so and so.exists():
                    service_ids.append(so.id)

        if service_ids or service_ref_json:
            try:
                work.with_context(skip_tmf_wiring=True).write(
                    {
                        "tmfc007_service_order_ref_json": service_ref_json,
                        "tmfc007_service_order_ids": [(6, 0, service_ids)],
                    }
                )
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception(
                    "TMFC007: failed to update Work %s service order links from WorkOrder event: %s",
                    ref_id,
                    exc,
                )


    # ------------------------------------------------------------------
    # TMF632 Party events
    # ------------------------------------------------------------------

    def handle_party_event(self, event_name, payload):
        if event_name not in TMFC007_PARTY_EVENTS:
            return
        self._log_received_event("party", event_name, payload)
        self._tmfc007_reconcile_party_event(payload, party_role=False)

    # ------------------------------------------------------------------
    # TMF669 PartyRole events
    # ------------------------------------------------------------------

    def handle_party_role_event(self, event_name, payload):
        if event_name not in TMFC007_PARTY_ROLE_EVENTS:
            return
        self._log_received_event("partyRole", event_name, payload)
        self._tmfc007_reconcile_party_event(payload, party_role=True)

    def _tmfc007_reconcile_party_event(self, payload, party_role=False):
        """Refresh ServiceOrder party links for any order touching this id.

        Best-effort and idempotent: locates ServiceOrders whose
        ``related_party`` JSON mentions the affected id, then re-runs
        ``_tmfc007_resolve_party_refs`` on that subset. Never mutates
        TMF641 payloads or URLs.
        """

        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        ServiceOrder = self.env["tmf.service.order"].sudo()
        try:
            affected = ServiceOrder.search([("related_party", "ilike", ref_id)])
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC007: party search failed for %s: %s", ref_id, exc)
            return

        if not affected:
            return

        try:
            affected._tmfc007_resolve_party_refs()
        except Exception as exc:  # pragma: no cover - best-effort
            _logger.exception(
                "TMFC007: party reconciliation failed for %s (%d orders): %s",
                ref_id,
                len(affected),
                exc,
            )


class TMFC007CommunicationWiring(models.Model):
    """TMFC007 dependency wiring for TMF681 CommunicationMessage.

    Adds JSON + relational links from communication messages back to
    ServiceOrders (TMF641) whenever the TMFC007 listeners see
    serviceOrder references inside CommunicationMessage events.
    """

    _inherit = "tmf.communication.message"

    tmfc007_service_order_ref_json = fields.Json(
        default=list,
        string="ServiceOrder refs JSON (TMF641)",
        help=(
            "Raw TMF641 ServiceOrder references observed in CommunicationMessage "
            "events. Kept for traceability; relational links below are the "
            "authoritative navigation surface inside Odoo."
        ),
    )

    tmfc007_service_order_ids = fields.Many2many(
        "tmf.service.order",
        "tmfc007_comm_message_service_order_rel",
        "communication_id",
        "service_order_id",
        string="Service Orders (TMF641)",
        help=(
            "Resolved TMF641 ServiceOrder records referenced from CommunicationMessage "
            "events.")
    )


class TMFC007WorkWiring(models.Model):
    """TMFC007 dependency wiring for TMF713 Work / TMF697 WorkOrder.

    TMFC007 treats TMF713 Work records as the local representation of
    TMF697 WorkOrders. This extension adds JSON + relational links from
    Work records back to ServiceOrders when TMFC007 listener callbacks
    observe serviceOrder references in incoming WorkOrder events.
    """

    _inherit = "tmf.work"

    tmfc007_service_order_ref_json = fields.Json(
        default=list,
        string="ServiceOrder refs JSON (TMF641)",
        help=(
            "Raw TMF641 ServiceOrder references observed in WorkOrder events. "
            "Kept for traceability; relational links below are the authoritative "
            "navigation surface inside Odoo."
        ),
    )

    tmfc007_service_order_ids = fields.Many2many(
        "tmf.service.order",
        "tmfc007_work_service_order_rel",
        "work_id",
        "service_order_id",
        string="Service Orders (TMF641)",
        help=(
            "Resolved TMF641 ServiceOrder records referenced from WorkOrder events."
        ),
    )

