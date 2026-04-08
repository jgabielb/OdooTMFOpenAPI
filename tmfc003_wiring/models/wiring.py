"""
TMFC003 — ProductOrderDeliveryOrchestrationAndManagement
=========================================================

Side-car wiring that connects the three-layer fulfillment chain:

    sale.order  (TMF622 ProductOrder)
        └──► tmf.service.order  (TMF641 ServiceOrder)  [One2many]
                  └──► tmf.resource.order  (TMF652 ResourceOrder)  [One2many]

Design decisions implemented here (as resolved by the architect):

1.  Orchestration trigger: explicit — fires when sale.order.tmf_status
    transitions TO "inProgress".
2.  tmf_service_inventory conflict: guarded by the context flag
    `skip_tmfc003_orchestration` so the legacy auto-creation path in
    tmf_service_inventory stays backward-compatible.
3.  State aggregation: "partial" until ALL child orders reach a terminal
    state, then "completed" (or "failed" if any failed).
4.  TMF622 double-publication guard: TMFC003 always writes child-driven
    state changes using the `skip_tmf_wiring` context flag and then
    emits its own explicit ProductOrderStateChangeEvent.
5.  Cross-catalog resolution: operates on pre-populated order items only.

Recursion guard
---------------
All internal writes that are NOT user-initiated must carry
``with_context(skip_tmf_wiring=True)``.  The outer hooks check this
flag before running any orchestration logic.
"""

import logging
import uuid
from datetime import datetime, timezone

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event sets handled by the listener controller
# ---------------------------------------------------------------------------

TMFC003_SERVICE_ORDER_EVENTS = {
    "ServiceOrderStateChangeEvent",
    "ServiceOrderCreateEvent",
    "ServiceOrderAttributeValueChangeEvent",
    "ServiceOrderDeleteEvent",
}

TMFC003_RESOURCE_ORDER_EVENTS = {
    "ResourceOrderStateChangeEvent",
    "ResourceOrderCreateEvent",
    "ResourceOrderAttributeValueChangeEvent",
    "ResourceOrderDeleteEvent",
}

# Terminal states for child orders
_TERMINAL_STATES = {"completed", "failed", "cancelled"}
_SUCCESS_STATES = {"completed"}
_FAILURE_STATES = {"failed", "cancelled"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_str(value):
    return str(value or "").strip()


# ---------------------------------------------------------------------------
# 1.  sale.order  ←→  tmf.service.order  wiring
# ---------------------------------------------------------------------------


class SaleOrderTMFC003Wiring(models.Model):
    """TMFC003 orchestration extensions for sale.order (TMF622 ProductOrder).

    Adds:
    - One2many link to tmf.service.order (the downstream service orders
      spawned for this product order).
    - Many2many link to tmf.process.flow (delivery orchestration flows).
    - delivery_state field for orchestration-level tracking.
    - Trigger logic: when tmf_status moves to "inProgress", spawn service
      orders from pre-populated order items.
    - State aggregation: aggregate child service-order states back to this
      product order and publish TMF622 ProductOrderStateChangeEvent.
    """

    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # TMFC003 fields
    # ------------------------------------------------------------------

    tmfc003_service_order_ids = fields.One2many(
        "tmf.service.order",
        "tmfc003_product_order_id",
        string="Service Orders (TMFC003)",
    )

    tmfc003_delivery_state = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("partial", "Partial"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        string="Delivery State (TMFC003)",
        default="not_started",
        index=True,
    )

    tmfc003_process_flow_ids = fields.Many2many(
        "tmf.process.flow",
        "tmfc003_sale_order_process_flow_rel",
        "sale_order_id",
        "process_flow_id",
        string="Delivery Process Flows (TMFC003 / TMF701)",
    )

    tmfc003_task_flow_ids = fields.Many2many(
        "tmf.task.flow",
        "tmfc003_sale_order_task_flow_rel",
        "sale_order_id",
        "task_flow_id",
        string="Delivery Task Flows (TMFC003 / TMF701)",
    )

    # ------------------------------------------------------------------
    # Orchestration trigger
    # ------------------------------------------------------------------

    def write(self, vals):
        """Intercept tmf_status → inProgress to launch delivery orchestration."""
        if self.env.context.get("skip_tmf_wiring"):
            return super().write(vals)

        previous_status = {}
        if "tmf_status" in vals:
            previous_status = {rec.id: (rec.tmf_status or "") for rec in self}

        res = super().write(vals)

        if "tmf_status" in vals and vals["tmf_status"] == "inProgress":
            for rec in self:
                prev = previous_status.get(rec.id, "")
                if prev != "inProgress" and not rec.env.context.get("skip_tmfc003_orchestration"):
                    rec._tmfc003_start_delivery_orchestration()

        return res

    # ------------------------------------------------------------------
    # Delivery orchestration spawn
    # ------------------------------------------------------------------

    def _tmfc003_start_delivery_orchestration(self):
        """Entry point: spawn service orders, create TMF701 flows.

        Called exactly once when tmf_status transitions to "inProgress".
        Guard: skip if service orders already exist for this product order.
        """
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}

        # Idempotency guard
        if self.tmfc003_service_order_ids:
            _logger.info("TMFC003: skipping spawn for SO %s — service orders already exist.", self.id)
            return

        _logger.info("TMFC003: starting delivery orchestration for sale.order %s", self.tmf_id or self.id)

        # Provision the TMF701 process flow first
        self._tmfc003_provision_delivery_process_flow()

        # Update delivery state
        self.with_context(**ctx).write({"tmfc003_delivery_state": "in_progress"})

        # Spawn one service order per distinct product line in this sale order
        self._tmfc003_spawn_service_orders()

    def _tmfc003_provision_delivery_process_flow(self):
        """Create a TMF701 process flow + task flow tracking this delivery."""
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}
        ProcessFlow = self.env["tmf.process.flow"].sudo()
        TaskFlow = self.env["tmf.task.flow"].sudo()

        pf_tmf_id = f"tmfc003-delivery-{self.tmf_id or self.id}"
        tf_tmf_id = f"tmfc003-delivery-task-{self.tmf_id or self.id}"

        process_flow = self.tmfc003_process_flow_ids[:1]
        if not process_flow:
            process_flow = ProcessFlow.search([("tmf_id", "=", pf_tmf_id)], limit=1)

        if not process_flow:
            process_flow = ProcessFlow.create({
                "tmf_id": pf_tmf_id,
                "name": f"Delivery orchestration for order {self.name or self.tmf_id or self.id}",
                "description": (
                    f"TMFC003 delivery process flow for product order {self.tmf_id or self.id}"
                ),
                "state": "inProgress",
                "related_party": self.partner_id.name and [
                    {"id": _safe_str(self.partner_id.tmf_id or self.partner_id.id), "name": self.partner_id.name}
                ] or [],
            })
        else:
            process_flow.with_context(**ctx).write({"state": "inProgress"})

        task_flow = self.tmfc003_task_flow_ids[:1]
        if not task_flow:
            task_flow = TaskFlow.search([("tmf_id", "=", tf_tmf_id)], limit=1)

        if not task_flow:
            task_flow = TaskFlow.create({
                "tmf_id": tf_tmf_id,
                "name": f"Order delivery fulfillment — {self.name or self.tmf_id or self.id}",
                "description": f"TMFC003 task flow for product order {self.tmf_id or self.id}",
                "state": "inProgress",
                "process_flow_id": process_flow.id,
            })
        else:
            task_flow.with_context(**ctx).write({"state": "inProgress"})

        self.with_context(**ctx).write({
            "tmfc003_process_flow_ids": [(4, process_flow.id)],
            "tmfc003_task_flow_ids": [(4, task_flow.id)],
        })

    def _tmfc003_spawn_service_orders(self):
        """Create tmf.service.order records from pre-populated order lines.

        Design decision 5: operates on pre-populated items only; no automatic
        spec traversal.  One service order is created per product group/line.
        """
        self.ensure_one()
        ServiceOrder = self.env["tmf.service.order"].sudo()
        ctx = {"skip_tmf_wiring": True}

        for line in self.order_line:
            product = line.product_id
            if not product:
                continue

            so = ServiceOrder.create({
                "description": (
                    f"Service order for {product.name or product.id} "
                    f"(product order {self.tmf_id or self.id})"
                ),
                "state": "acknowledged",
                "partner_id": self.partner_id.id if self.partner_id else False,
                "tmfc003_product_order_id": self.id,
                "service_order_item": [
                    {
                        "id": _safe_str(uuid.uuid4()),
                        "action": "add",
                        "quantity": int(line.product_uom_qty or 1),
                        "service": {
                            "name": product.name or "",
                            "serviceType": "CFS",
                        },
                    }
                ],
            })
            _logger.info("TMFC003: created tmf.service.order %s for line %s", so.tmf_id, line.id)

    # ------------------------------------------------------------------
    # State aggregation (called by ServiceOrderTMFC003Wiring)
    # ------------------------------------------------------------------

    def _tmfc003_aggregate_from_service_orders(self):
        """Recompute delivery_state and tmf_status from all child service orders.

        Idempotent — safe to call multiple times (e.g. race condition on
        parallel service order completions).
        """
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}

        service_orders = self.tmfc003_service_order_ids
        if not service_orders:
            return

        states = {so.state for so in service_orders}
        all_terminal = all(s in _TERMINAL_STATES for s in states)
        any_failed = bool(states & _FAILURE_STATES)
        all_success = all(s in _SUCCESS_STATES for s in states)

        if not all_terminal:
            new_delivery_state = "partial" if (states & _SUCCESS_STATES) else "in_progress"
            new_tmf_status = "inProgress"
        elif all_success:
            new_delivery_state = "completed"
            new_tmf_status = "completed"
        elif any_failed:
            new_delivery_state = "failed"
            new_tmf_status = "failed"
        else:
            new_delivery_state = "completed"
            new_tmf_status = "completed"

        old_tmf_status = self.tmf_status
        old_delivery_state = self.tmfc003_delivery_state

        if new_delivery_state != old_delivery_state or new_tmf_status != old_tmf_status:
            self.with_context(**ctx).write({
                "tmfc003_delivery_state": new_delivery_state,
                "tmf_status": new_tmf_status,
            })
            _logger.info(
                "TMFC003: sale.order %s delivery_state=%s tmf_status=%s",
                self.tmf_id or self.id, new_delivery_state, new_tmf_status,
            )
            # Update TMF701 process flow state
            self._tmfc003_sync_process_flow_state(new_tmf_status)
            # Publish explicit TMF622 ProductOrderStateChangeEvent
            self._tmfc003_notify_product_order_state_change()

        # On completion, update product inventory
        if new_tmf_status == "completed":
            self._tmfc003_update_product_inventory_on_completion()

    def _tmfc003_sync_process_flow_state(self, tmf_status):
        """Mirror product order TMF status into the TMFC003 process/task flows."""
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}
        flow_state_map = {
            "inProgress": "inProgress",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        flow_state = flow_state_map.get(tmf_status, "inProgress")

        for pf in self.tmfc003_process_flow_ids:
            pf.with_context(**ctx).write({"state": flow_state})
        for tf in self.tmfc003_task_flow_ids:
            tf.with_context(**ctx).write({"state": flow_state})

    def _tmfc003_notify_product_order_state_change(self):
        """Publish ProductOrderStateChangeEvent via tmf.hub.subscription.

        Uses the existing _notify infrastructure on sale.order if available,
        otherwise falls back to direct hub publication.
        """
        self.ensure_one()
        try:
            hub = self.env["tmf.hub.subscription"].sudo()
            resource_json = self.to_tmf_json()
            hub._notify_subscribers(
                "productOrder",
                "ProductOrderStateChangeEvent",
                resource_json,
            )
        except Exception as exc:
            _logger.warning("TMFC003: failed to publish ProductOrderStateChangeEvent: %s", exc)

    # ------------------------------------------------------------------
    # Product inventory update on delivery completion
    # ------------------------------------------------------------------

    def _tmfc003_update_product_inventory_on_completion(self):
        """Update tmf.product records when a product order delivery completes.

        Finds tmf.product records that reference this product order (via
        product_order_ref_json) and sets their status to 'active'.
        """
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}
        order_tmf_id = _safe_str(self.tmf_id or self.id)

        if not order_tmf_id:
            return

        TmfProduct = self.env["tmf.product"].sudo()
        # Search by product_order_ref_json (TMFC005 pattern) or direct link
        candidates = TmfProduct.search([])
        updated = 0
        for prod in candidates:
            order_refs = prod.product_order_ref_json or []
            if isinstance(order_refs, dict):
                order_refs = [order_refs]
            if any(
                isinstance(item, dict) and _safe_str(item.get("id")) == order_tmf_id
                for item in order_refs
            ):
                if prod.status != "active":
                    prod.with_context(**ctx).write({"status": "active"})
                    updated += 1

        if updated:
            _logger.info(
                "TMFC003: updated %d tmf.product records to 'active' on completion of sale.order %s",
                updated, order_tmf_id,
            )


# ---------------------------------------------------------------------------
# 2.  tmf.service.order  ←→  sale.order / tmf.resource.order  wiring
# ---------------------------------------------------------------------------


class ServiceOrderTMFC003Wiring(models.Model):
    """TMFC003 orchestration extensions for tmf.service.order (TMF641).

    Adds:
    - Many2one link back to the originating sale.order (product order).
    - One2many link to tmf.resource.order records spawned from this service order.
    - Overrides write() to detect terminal state transitions and propagate
      state up to the parent product order.
    - Spawns resource orders from service order items.
    """

    _inherit = "tmf.service.order"

    # ------------------------------------------------------------------
    # TMFC003 fields
    # ------------------------------------------------------------------

    tmfc003_product_order_id = fields.Many2one(
        "sale.order",
        string="Product Order (TMFC003)",
        index=True,
        ondelete="set null",
    )

    tmfc003_resource_order_ids = fields.One2many(
        "tmf.resource.order",
        "tmfc003_service_order_id",
        string="Resource Orders (TMFC003)",
    )

    # Raw JSON ref storage for cross-order resolution (aligned with TMFC003 analysis)
    tmfc003_product_order_ref_json = fields.Json(
        default=dict,
        string="Product Order ref JSON (TMFC003)",
    )

    # ------------------------------------------------------------------
    # State propagation
    # ------------------------------------------------------------------

    def write(self, vals):
        """Detect terminal state transitions and propagate to parent product order."""
        if self.env.context.get("skip_tmf_wiring"):
            return super().write(vals)

        previous_states = {}
        if "state" in vals:
            previous_states = {rec.id: (rec.state or "") for rec in self}

        res = super().write(vals)

        if "state" in vals:
            for rec in self:
                new_state = rec.state or ""
                old_state = previous_states.get(rec.id, "")
                if new_state != old_state and new_state in _TERMINAL_STATES:
                    rec._tmfc003_propagate_state_to_product_order()
                # Always publish explicit ServiceOrderStateChangeEvent on state change
                if new_state != old_state:
                    rec._tmfc003_notify_service_order_state_change()

        return res

    def _tmfc003_propagate_state_to_product_order(self):
        """If all sibling service orders are terminal, aggregate product order state."""
        self.ensure_one()
        product_order = self.tmfc003_product_order_id
        if not product_order or not product_order.exists():
            return
        # Delegate aggregation to sale.order — idempotent
        product_order._tmfc003_aggregate_from_service_orders()

    def _tmfc003_notify_service_order_state_change(self):
        """Publish ServiceOrderStateChangeEvent explicitly (TMFC003-sourced transition)."""
        self.ensure_one()
        try:
            hub = self.env["tmf.hub.subscription"].sudo()
            hub._notify_subscribers(
                "serviceOrder",
                "ServiceOrderStateChangeEvent",
                self.to_tmf_json(),
            )
        except Exception as exc:
            _logger.warning("TMFC003: failed to publish ServiceOrderStateChangeEvent: %s", exc)

    # ------------------------------------------------------------------
    # Resource order spawn
    # ------------------------------------------------------------------

    def _tmfc003_spawn_resource_orders(self):
        """Create tmf.resource.order records from this service order's items.

        Design decision 5: operates on pre-populated items only — no spec traversal.
        Called after the service order transitions to "inProgress".
        """
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}
        ResourceOrder = self.env["tmf.resource.order"].sudo()

        if self.tmfc003_resource_order_ids:
            _logger.info("TMFC003: skipping resource order spawn for %s — already exist.", self.tmf_id)
            return

        items = self.service_order_item or []
        if not isinstance(items, list):
            items = []

        if not items:
            # No service items — mark service order completed immediately
            _logger.info(
                "TMFC003: service order %s has no items — auto-completing.", self.tmf_id
            )
            self.with_context(**ctx).write({"state": "completed"})
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            service_info = item.get("service") or {}
            item_id_str = _safe_str(item.get("id") or uuid.uuid4())

            ro = ResourceOrder.create({
                "name": (
                    f"Resource order for {service_info.get('name', '')} "
                    f"(service order {self.tmf_id or self.id})"
                ),
                "description": (
                    f"TMFC003 resource order for service order item {item_id_str}"
                ),
                "state": "acknowledged",
                "partner_id": self.partner_id.id if self.partner_id else False,
                "tmfc003_service_order_id": self.id,
                "order_item_ids": [
                    (0, 0, {
                        "item_id": _safe_str(uuid.uuid4()),
                        "action": "add",
                        "quantity": int(item.get("quantity") or 1),
                    })
                ],
            })
            _logger.info(
                "TMFC003: created tmf.resource.order %s for service order item %s",
                ro.tmf_id, item_id_str,
            )

    # ------------------------------------------------------------------
    # State aggregation (called by ResourceOrderTMFC003Wiring)
    # ------------------------------------------------------------------

    def _tmfc003_aggregate_from_resource_orders(self):
        """Recompute this service order's state from all child resource orders."""
        self.ensure_one()
        ctx = {"skip_tmf_wiring": True}

        resource_orders = self.tmfc003_resource_order_ids
        if not resource_orders:
            return

        states = {ro.state for ro in resource_orders}
        all_terminal = all(s in _TERMINAL_STATES for s in states)
        any_failed = bool(states & _FAILURE_STATES)
        all_success = all(s in _SUCCESS_STATES for s in states)

        if not all_terminal:
            new_state = "inProgress"
        elif all_success:
            new_state = "completed"
        elif any_failed:
            new_state = "failed"
        else:
            new_state = "completed"

        old_state = self.state or ""
        if new_state != old_state:
            self.with_context(**ctx).write({"state": new_state})
            _logger.info(
                "TMFC003: tmf.service.order %s aggregated state → %s",
                self.tmf_id or self.id, new_state,
            )


# ---------------------------------------------------------------------------
# 3.  tmf.resource.order  ←→  tmf.service.order  wiring
# ---------------------------------------------------------------------------


class ResourceOrderTMFC003Wiring(models.Model):
    """TMFC003 orchestration extensions for tmf.resource.order (TMF652).

    Adds:
    - Many2one link back to the originating tmf.service.order.
    - Overrides write() to detect terminal state transitions and propagate
      state up to the parent service order.
    """

    _inherit = "tmf.resource.order"

    # ------------------------------------------------------------------
    # TMFC003 fields
    # ------------------------------------------------------------------

    tmfc003_service_order_id = fields.Many2one(
        "tmf.service.order",
        string="Service Order (TMFC003)",
        index=True,
        ondelete="set null",
    )

    # Raw JSON ref storage for cross-order resolution
    tmfc003_service_order_ref_json = fields.Json(
        default=dict,
        string="Service Order ref JSON (TMFC003)",
    )

    # ------------------------------------------------------------------
    # State propagation
    # ------------------------------------------------------------------

    def write(self, vals):
        """Detect terminal state transitions and propagate to parent service order."""
        if self.env.context.get("skip_tmf_wiring"):
            return super().write(vals)

        previous_states = {}
        if "state" in vals:
            previous_states = {rec.id: (rec.state or "") for rec in self}

        res = super().write(vals)

        if "state" in vals:
            for rec in self:
                new_state = rec.state or ""
                old_state = previous_states.get(rec.id, "")
                if new_state != old_state and new_state in _TERMINAL_STATES:
                    rec._tmfc003_propagate_state_to_service_order()
                if new_state != old_state:
                    rec._tmfc003_notify_resource_order_state_change()

        return res

    def _tmfc003_propagate_state_to_service_order(self):
        """If all sibling resource orders are terminal, aggregate service order state."""
        self.ensure_one()
        service_order = self.tmfc003_service_order_id
        if not service_order or not service_order.exists():
            return
        service_order._tmfc003_aggregate_from_resource_orders()

    def _tmfc003_notify_resource_order_state_change(self):
        """Publish ResourceOrderStateChangeEvent explicitly."""
        self.ensure_one()
        try:
            hub = self.env["tmf.hub.subscription"].sudo()
            hub._notify_subscribers(
                "resourceOrder",
                "ResourceOrderStateChangeEvent",
                self.to_tmf_json(),
            )
        except Exception as exc:
            _logger.warning("TMFC003: failed to publish ResourceOrderStateChangeEvent: %s", exc)


# ---------------------------------------------------------------------------
# 4.  TMFC003WiringTools — reconciliation tools AbstractModel
# ---------------------------------------------------------------------------


class TMFC003WiringTools(models.AbstractModel):
    """TMFC003 Wiring Reconciliation Tools.

    Handles incoming TMF641/TMF652 events from external systems
    (hub subscriber callbacks) and reconciles local Odoo state.

    Listener routes in controllers.py dispatch to methods here.
    """

    _name = "tmfc003.wiring.tools"
    _description = "TMFC003 Wiring Reconciliation Tools"

    # ------------------------------------------------------------------
    # Helpers (aligned with TMFC005 pattern)
    # ------------------------------------------------------------------

    def _extract_event_resource(self, payload):
        """Extract the event resource dict from a TMF event envelope."""
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("event"), dict):
            event = payload["event"]
            for key in ("serviceOrder", "resourceOrder", "service", "resource"):
                if isinstance(event.get(key), dict):
                    return event[key]
        for key in ("serviceOrder", "resourceOrder"):
            if isinstance(payload.get(key), dict):
                return payload[key]
        return payload

    def _extract_resource_id(self, payload):
        """Extract the TMF id from an event payload."""
        resource = self._extract_event_resource(payload)
        return _safe_str(resource.get("id") or payload.get("id") or "")

    def _extract_event_type(self, payload):
        """Extract eventType from the event envelope."""
        if not isinstance(payload, dict):
            return ""
        return _safe_str(payload.get("eventType") or "")

    def _extract_new_state(self, payload):
        """Extract the new state from a state-change event."""
        resource = self._extract_event_resource(payload)
        return _safe_str(resource.get("state") or "")

    # ------------------------------------------------------------------
    # TMF641 ServiceOrder event handlers
    # ------------------------------------------------------------------

    def _reconcile_service_order_state_change(self, payload=None):
        """Handle ServiceOrderStateChangeEvent: update local tmf.service.order state
        and propagate up to the parent product order if terminal.
        """
        payload = payload or {}
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            _logger.warning("TMFC003: ServiceOrderStateChangeEvent received without resource id")
            return

        new_state = self._extract_new_state(payload)
        if not new_state:
            _logger.warning(
                "TMFC003: ServiceOrderStateChangeEvent for %s has no state — skipping", ref_id
            )
            return

        service_order = self.env["tmf.service.order"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1
        )
        if not service_order:
            _logger.info(
                "TMFC003: ServiceOrderStateChangeEvent — no local record for tmf_id=%s", ref_id
            )
            return

        old_state = service_order.state or ""
        if old_state == new_state:
            return

        ctx = {"skip_tmf_wiring": True}
        service_order.with_context(**ctx).write({"state": new_state})
        _logger.info(
            "TMFC003: tmf.service.order %s state %s → %s (via listener)",
            ref_id, old_state, new_state,
        )

        # Propagate upward if terminal
        if new_state in _TERMINAL_STATES and service_order.tmfc003_product_order_id:
            service_order.tmfc003_product_order_id._tmfc003_aggregate_from_service_orders()

    def _reconcile_service_order_create(self, payload=None):
        """Handle ServiceOrderCreateEvent: resolve back-reference to product order if present."""
        payload = payload or {}
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        service_order = self.env["tmf.service.order"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1
        )
        if not service_order:
            return

        resource = self._extract_event_resource(payload)
        self._resolve_tmf_refs_on_service_order(service_order, resource)

    def _reconcile_service_order_attribute_change(self, payload=None):
        """Handle ServiceOrderAttributeValueChangeEvent: re-resolve refs."""
        self._reconcile_service_order_create(payload)

    def _reconcile_service_order_delete(self, payload=None):
        """Handle ServiceOrderDeleteEvent: remove the record or mark it deleted."""
        payload = payload or {}
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        service_order = self.env["tmf.service.order"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1
        )
        if not service_order:
            return

        product_order = service_order.tmfc003_product_order_id
        ctx = {"skip_tmf_wiring": True}
        service_order.with_context(**ctx).write({"state": "cancelled"})
        _logger.info("TMFC003: marked service order %s as cancelled on delete event.", ref_id)

        if product_order and product_order.exists():
            product_order._tmfc003_aggregate_from_service_orders()

    # ------------------------------------------------------------------
    # TMF652 ResourceOrder event handlers
    # ------------------------------------------------------------------

    def _reconcile_resource_order_state_change(self, payload=None):
        """Handle ResourceOrderStateChangeEvent: update local tmf.resource.order state
        and propagate up to parent service order and product order.
        """
        payload = payload or {}
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            _logger.warning("TMFC003: ResourceOrderStateChangeEvent received without resource id")
            return

        new_state = self._extract_new_state(payload)
        if not new_state:
            _logger.warning(
                "TMFC003: ResourceOrderStateChangeEvent for %s has no state — skipping", ref_id
            )
            return

        resource_order = self.env["tmf.resource.order"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1
        )
        if not resource_order:
            _logger.info(
                "TMFC003: ResourceOrderStateChangeEvent — no local record for tmf_id=%s", ref_id
            )
            return

        old_state = resource_order.state or ""
        if old_state == new_state:
            return

        ctx = {"skip_tmf_wiring": True}
        resource_order.with_context(**ctx).write({"state": new_state})
        _logger.info(
            "TMFC003: tmf.resource.order %s state %s → %s (via listener)",
            ref_id, old_state, new_state,
        )

        # Propagate upward if terminal
        if new_state in _TERMINAL_STATES and resource_order.tmfc003_service_order_id:
            service_order = resource_order.tmfc003_service_order_id
            service_order._tmfc003_aggregate_from_resource_orders()
            if service_order.state in _TERMINAL_STATES and service_order.tmfc003_product_order_id:
                service_order.tmfc003_product_order_id._tmfc003_aggregate_from_service_orders()

    def _reconcile_resource_order_create(self, payload=None):
        """Handle ResourceOrderCreateEvent: resolve back-reference to service order if present."""
        payload = payload or {}
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        resource_order = self.env["tmf.resource.order"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1
        )
        if not resource_order:
            return

        resource = self._extract_event_resource(payload)
        self._resolve_tmf_refs_on_resource_order(resource_order, resource)

    def _reconcile_resource_order_attribute_change(self, payload=None):
        """Handle ResourceOrderAttributeValueChangeEvent: re-resolve refs."""
        self._reconcile_resource_order_create(payload)

    def _reconcile_resource_order_delete(self, payload=None):
        """Handle ResourceOrderDeleteEvent: mark record cancelled and re-aggregate."""
        payload = payload or {}
        ref_id = self._extract_resource_id(payload)
        if not ref_id:
            return

        resource_order = self.env["tmf.resource.order"].sudo().search(
            [("tmf_id", "=", ref_id)], limit=1
        )
        if not resource_order:
            return

        service_order = resource_order.tmfc003_service_order_id
        ctx = {"skip_tmf_wiring": True}
        resource_order.with_context(**ctx).write({"state": "cancelled"})
        _logger.info("TMFC003: marked resource order %s as cancelled on delete event.", ref_id)

        if service_order and service_order.exists():
            service_order._tmfc003_aggregate_from_resource_orders()
            if service_order.state in _TERMINAL_STATES and service_order.tmfc003_product_order_id:
                service_order.tmfc003_product_order_id._tmfc003_aggregate_from_service_orders()

    # ------------------------------------------------------------------
    # Cross-order reference resolution
    # ------------------------------------------------------------------

    def _resolve_tmf_refs(self, model_name, tmf_id, resource_payload):
        """Generic cross-order reference resolver.

        Looks for product_order / service_order references in the resource
        payload and wires them to local records.
        """
        if not tmf_id or not isinstance(resource_payload, dict):
            return

        if model_name == "tmf.service.order":
            record = self.env["tmf.service.order"].sudo().search(
                [("tmf_id", "=", tmf_id)], limit=1
            )
            if record:
                self._resolve_tmf_refs_on_service_order(record, resource_payload)

        elif model_name == "tmf.resource.order":
            record = self.env["tmf.resource.order"].sudo().search(
                [("tmf_id", "=", tmf_id)], limit=1
            )
            if record:
                self._resolve_tmf_refs_on_resource_order(record, resource_payload)

    def _resolve_tmf_refs_on_service_order(self, service_order, resource_payload):
        """Wire product_order_id on a service order from its payload."""
        if service_order.tmfc003_product_order_id:
            return
        ctx = {"skip_tmf_wiring": True}
        updates = {}

        # Check for productOrder ref in payload
        po_ref = resource_payload.get("productOrder") or resource_payload.get("productOrderRef") or {}
        if isinstance(po_ref, dict):
            po_id = _safe_str(po_ref.get("id") or "")
            if po_id:
                so = self.env["sale.order"].sudo().search([("tmf_id", "=", po_id)], limit=1)
                if so:
                    updates["tmfc003_product_order_id"] = so.id
                    updates["tmfc003_product_order_ref_json"] = po_ref

        if updates:
            service_order.with_context(**ctx).write(updates)

    def _resolve_tmf_refs_on_resource_order(self, resource_order, resource_payload):
        """Wire service_order_id on a resource order from its payload."""
        if resource_order.tmfc003_service_order_id:
            return
        ctx = {"skip_tmf_wiring": True}
        updates = {}

        # Check for serviceOrder ref in payload
        so_ref = resource_payload.get("serviceOrder") or resource_payload.get("serviceOrderRef") or {}
        if isinstance(so_ref, dict):
            so_id = _safe_str(so_ref.get("id") or "")
            if so_id:
                svo = self.env["tmf.service.order"].sudo().search([("tmf_id", "=", so_id)], limit=1)
                if svo:
                    updates["tmfc003_service_order_id"] = svo.id
                    updates["tmfc003_service_order_ref_json"] = so_ref

        if updates:
            resource_order.with_context(**ctx).write(updates)

    # ------------------------------------------------------------------
    # Unified event dispatcher (used by controller)
    # ------------------------------------------------------------------

    def handle_service_order_event(self, event_name, payload=None):
        """Dispatch incoming TMF641 service order events to the right handler."""
        handlers = {
            "ServiceOrderStateChangeEvent": self._reconcile_service_order_state_change,
            "ServiceOrderCreateEvent": self._reconcile_service_order_create,
            "ServiceOrderAttributeValueChangeEvent": self._reconcile_service_order_attribute_change,
            "ServiceOrderDeleteEvent": self._reconcile_service_order_delete,
        }
        handler = handlers.get(event_name)
        if handler:
            handler(payload or {})
        else:
            _logger.warning("TMFC003: unhandled service order event: %s", event_name)

    def handle_resource_order_event(self, event_name, payload=None):
        """Dispatch incoming TMF652 resource order events to the right handler."""
        handlers = {
            "ResourceOrderStateChangeEvent": self._reconcile_resource_order_state_change,
            "ResourceOrderCreateEvent": self._reconcile_resource_order_create,
            "ResourceOrderAttributeValueChangeEvent": self._reconcile_resource_order_attribute_change,
            "ResourceOrderDeleteEvent": self._reconcile_resource_order_delete,
        }
        handler = handlers.get(event_name)
        if handler:
            handler(payload or {})
        else:
            _logger.warning("TMFC003: unhandled resource order event: %s", event_name)
