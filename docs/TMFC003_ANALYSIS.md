# TMFC003 — ProductOrderDeliveryOrchestrationAndManagement
## Analysis Document

**Date:** 2026-04-07
**Analyst:** Principal Software Architect (subagent session: tmfc003-analysis)
**Status:** Pre-implementation analysis — no code changes made
**Repo baseline:** TMFC005 and TMFC027 fully wired; TMFC003 has zero wiring.

---

## 1. TMFC003 YAML Scope Summary

### 1.1 Component Identity

| Field | Value |
|-------|-------|
| TMFC ID | TMFC003 |
| Name | ProductOrderDeliveryOrchestrationAndManagement |
| Functional Block | CoreCommerce (Production boundary) |
| Role in ODA | Orchestrates the delivery chain from a confirmed ProductOrder to ServiceOrder → ResourceOrder, tracking fulfillment state across the product/service/resource layers. |

### 1.2 Exposed APIs (what TMFC003 serves)

These are the APIs this component is responsible for exposing to other ODA components:

| TMF ID | API Name | Key Resources | Operations | Notes |
|--------|----------|---------------|------------|-------|
| TMF622 | product-ordering-management-api | productOrder, cancelProductOrder | GET, GET /id, POST, PATCH, DELETE | This component is a **consumer and publisher** of productOrder state — it drives orders into fulfillment and publishes state-change events |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | TMFC003 uses process/task flows to model the orchestration graph for each order delivery |

### 1.3 Dependent APIs (what TMFC003 calls/relies on)

| TMF ID | API Name | Required? | Key Resources | Purpose in TMFC003 |
|--------|----------|-----------|---------------|---------------------|
| TMF620 | product-catalog-management-api | false | productOffering, productSpecification | Resolve what product specs are referenced by the order to determine what services/resources must be provisioned |
| TMF622 | product-ordering-management-api | true | productOrder | Source of the orchestrated order; TMFC003 reacts to confirmed orders from TMFC002 |
| TMF633 | service-catalog-management-api | false | serviceSpecification | Determine what service specification(s) must be created by the service order |
| TMF634 | resource-catalog-management-api | false | resourceSpecification | Determine what resource specification(s) must be allocated in the resource order |
| TMF637 | product-inventory-management-api | true | product | Create/update product inventory records upon delivery completion |
| TMF638 | service-inventory-management-api | false | service | Check and update resulting service inventory entries after service order completion |
| TMF639 | resource-inventory-management-api | false | resource | Check and update resulting resource inventory entries after resource order completion |
| TMF641 | service-order-management-api | true | serviceOrder, cancelServiceOrder | Create service orders as sub-tasks of product order delivery; subscribe to their state changes |
| TMF652 | resource-order-management-api | true | resourceOrder, cancelResourceOrder | Create resource orders as sub-tasks of product order delivery; subscribe to their state changes |
| TMF701 | process-flow-management-api | false | processFlow, taskFlow | Track orchestration progress across the delivery chain |

### 1.4 Published Events (what TMFC003 emits)

| TMF ID | Hub / API | Event Names | Trigger |
|--------|-----------|-------------|---------|
| TMF622 | ProductOrderManagement | ProductOrderStateChangeEvent | When product order state transitions (e.g., acknowledged → inProgress → completed) driven by downstream service/resource order state |
| TMF622 | ProductOrderManagement | ProductOrderAttributeValueChangeEvent | When non-state fields on the order are updated during delivery tracking |
| TMF622 | ProductOrderManagement | ProductOrderInformationRequiredEvent | When the delivery chain stalls and human/system input is needed |
| TMF701 | ProcessFlowManagement | processFlowCreateEvent, processFlowStateChangeEvent, processFlowDeleteEvent, processFlowAttributeValueChangeEvent | When process flows are created/updated to track orchestration steps |
| TMF701 | ProcessFlowManagement | taskFlowCreateEvent, taskFlowStateChangeEvent, taskFlowDeleteEvent, taskFlowAttributeValueChangeEvent, taskFlowInformationRequiredEvent | Per-step task flows within the delivery orchestration |

### 1.5 Subscribed Events (what TMFC003 listens to)

| TMF ID | Source Component | Event Names | Handler Purpose |
|--------|-----------------|-------------|-----------------|
| TMF641 | ServiceOrderManagement (TMFC007) | ServiceOrderStateChangeEvent, ServiceOrderAttributeValueChangeEvent, ServiceOrderCreateEvent, ServiceOrderDeleteEvent | React to service order completion/failure → propagate state up to ProductOrder and ProcessFlow |
| TMF652 | ResourceOrderManagement (TMFC011) | ResourceOrderStateChangeEvent, ResourceOrderAttributeValueChangeEvent, ResourceOrderCreateEvent, ResourceOrderDeleteEvent | React to resource order completion/failure → propagate state up to ServiceOrder and ProductOrder |

---

## 2. Existing Odoo Models and Controllers Mapping to TMFC003 Resources

### 2.1 Product Order (TMF622) — **tmf_product_ordering**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| productOrder | `sale.order` (extended by `tmf.model.mixin`) | ✅ Full CRUD via `ordering_controller.py` |
| cancelProductOrder | `tmf.cancel.product.order` | ✅ Modeled in `sale_order.py` |
| ProductOrder events (create/update/delete/stateChange) | Hooks in `sale.order.create/write/unlink` | ✅ Publish via `tmf.hub.subscription._notify_subscribers` |

**Gap for TMFC003:** `sale.order` does **not** hold references to downstream `tmf.service.order` or `tmf.resource.order`. There is no orchestration linkage connecting a confirmed product order to service/resource orders in Odoo.

### 2.2 Service Order (TMF641) — **tmf_service_order**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| serviceOrder | `tmf.service.order` | ✅ Full CRUD via `main_controller.py` (TMF641 v4) |
| cancelServiceOrder | Not found | ❌ Missing |
| ServiceOrder events (create/update/delete) | `_notify()` in `main_model.py` | ✅ Partial — create/update/delete events; no stateChange specialization |

**Link to ProductOrder:** `tmf.service.order` has **no** `sale_order_id` or `product_order_id` foreign key. It does have `partner_id` and `project_task_id` for Odoo-side fulfillment.

### 2.3 Resource Order (TMF652) — **tmf_resource_order**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| resourceOrder | `tmf.resource.order` | ✅ Full CRUD via `main_controller.py` (TMF652 v4) |
| cancelResourceOrder | Not found | ❌ Missing |
| ResourceOrder events (create/update/delete) | `_notify()` in `main_model.py` | ✅ Partial — create/update/delete; no explicit stateChange event |

**Link to ServiceOrder/ProductOrder:** `tmf.resource.order` has `partner_id`, `project_task_id`, `picking_id` for Odoo-side fulfillment. **No** `service_order_id` or `product_order_id` foreign key.

### 2.4 Service Inventory (TMF638) — **tmf_service_inventory**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| service | `tmf.service` | ✅ Model exists, linked to `sale.order` via `order_line_id` |

**Auto-creation:** `sale_order.py` in `tmf_service_inventory` auto-creates `tmf.service` records on `action_confirm()`. This is a rudimentary integration, not ODA-grade orchestration wiring.

### 2.5 Resource Inventory (TMF639) — **tmf_resource_inventory**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| resource | `stock.lot` (extended) and `tmf.service` extended with `resource_id` | ⚠️ Partial — stock lot as resource, no TMF639 controller verified |

### 2.6 Product Inventory (TMF637) — **tmf_product_inventory / tmf_product**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| product | `tmf.product` | ✅ Full CRUD; enriched by TMFC005 wiring |

**Gap for TMFC003:** TMFC003 needs to update `tmf.product` records upon order delivery completion — this update path is not currently driven by service/resource order state.

### 2.7 Process Flow (TMF701) — **tmf_process_flow**

| TMF Resource | Odoo Model / Controller | State |
|--------------|------------------------|-------|
| processFlow | `tmf.process.flow` (inherits `tmf.process.flow.mixin`) | ✅ Model + events exist |
| taskFlow | `tmf.task.flow` (inherits `tmf.process.flow.mixin`) | ✅ Model + events exist |

**Gap for TMFC003:** No delivery-specific process/task flows are provisioned per product order. TMFC005 and TMFC027 already provision TMF701 flows — TMFC003 needs the same pattern for order delivery orchestration.

---

## 3. Gap Analysis: What Exists vs. What Needs to Be Built

### 3.1 Summary Matrix

| Capability Area | Exists? | Gap |
|-----------------|---------|-----|
| TMF622 productOrder CRUD | ✅ Yes (`sale.order` + `ordering_controller.py`) | No orchestration trigger on order confirmation |
| TMF641 serviceOrder CRUD | ✅ Yes (`tmf.service.order` + `main_controller.py`) | No link back to productOrder; no stateChange event propagation to productOrder |
| TMF652 resourceOrder CRUD | ✅ Yes (`tmf.resource.order` + `main_controller.py`) | No link back to serviceOrder or productOrder; no state propagation up |
| ProductOrder → ServiceOrder linkage | ❌ No | Needs `product_order_id` FK on `tmf.service.order` and creation logic |
| ServiceOrder → ResourceOrder linkage | ❌ No | Needs `service_order_id` FK on `tmf.resource.order` and creation logic |
| ServiceOrder stateChange → ProductOrder state | ❌ No | Needs listener endpoint + callback logic |
| ResourceOrder stateChange → ServiceOrder/ProductOrder state | ❌ No | Needs listener endpoint + callback logic |
| TMF641 event subscription (TMFC003 as consumer) | ❌ No | No `/tmfc003/listener/serviceOrder` route exists |
| TMF652 event subscription (TMFC003 as consumer) | ❌ No | No `/tmfc003/listener/resourceOrder` route exists |
| TMF622 stateChange publication from orchestration | ⚠️ Partial | Sale order publishes stateChange but it's TMFC002's hook, not orchestration-driven |
| TMF701 process/task flow per delivery | ❌ No | No flow provisioning tied to order delivery lifecycle |
| Product inventory update on delivery completion | ❌ No | `tmf.product` not updated by service/resource order state |
| cancelServiceOrder / cancelResourceOrder | ❌ No | Neither sub-resource exists in current modules |
| TMF620/633/634 ref resolution for delivery context | ❌ No | No wiring resolves product spec → service spec → resource spec chains |
| Hub registration for TMFC003 listener routes | ❌ No | TMFC003 does not register its listener endpoints for subscribed events |

### 3.2 Critical Gaps (blockers for TMFC003 to be "fully wired")

1. **No orchestration linkage** between `sale.order` → `tmf.service.order` → `tmf.resource.order`. These three models are islands with no FK relationships across them.

2. **No upstream event propagation.** When a `tmf.resource.order` changes state to `completed`, nothing causes the parent `tmf.service.order` to advance, which in turn should drive the `sale.order` to `completed`.

3. **No subscribed-event consumer routes.** TMFC003 must have listener endpoints for TMF641 (`ServiceOrderStateChangeEvent`) and TMF652 (`ResourceOrderStateChangeEvent`) to implement the orchestration callbacks. None exist.

4. **No TMF701 flow provisioning for delivery.** Unlike TMFC005 (which provisions flows per product inventory item) and TMFC027 (which provisions flows per qualification), TMFC003 has no flow-per-order logic.

5. **No `tmfc003_wiring` addon.** The side-car wiring addon does not exist at all.

### 3.3 Secondary Gaps (required for completeness)

6. **Missing `cancelServiceOrder` and `cancelResourceOrder` models.** The YAML specs for TMF641/TMF652 include cancellation sub-resources, but no Odoo models exist for them.

7. **No service-spec → resource-spec orchestration resolution.** TMFC003 needs to understand, from a product offering, which service specifications and resource specifications must be fulfilled. Currently `tmf.service.order` and `tmf.resource.order` are created manually, not driven from product specification chains.

8. **Rudimentary service inventory auto-creation.** The `tmf_service_inventory` module auto-creates `tmf.service` on `sale.order.action_confirm()`. This bypasses the TMF641/TMF652 orchestration path entirely and conflicts with the proper TMFC003 model.

9. **Stale `tmf_resource_inventory` dependency chain.** Resource inventory (`stock.lot` extension) does not have ODA-grade event publication for `resourceDeleteEvent`, which TMFC003 completion logic will depend on.

---

## 4. Proposed Implementation Plan

### 4.1 Addon Structure

Create one new addon:

```
tmfc003_wiring/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   └── wiring.py          ← side-car wiring on sale.order, tmf.service.order, tmf.resource.order
├── controllers/
│   ├── __init__.py
│   └── controllers.py     ← listener routes for TMF641 + TMF652 events
└── tools/
    ├── __init__.py
    └── tools.py           ← TMFC003WiringTools AbstractModel
```

### 4.2 Files to Create

#### `tmfc003_wiring/__manifest__.py`

```python
{
    "name": "TMFC003 Wiring - ProductOrderDeliveryOrchestrationAndManagement",
    "version": "1.0.0",
    "category": "TMF/ODA",
    "depends": [
        "tmf_product_ordering",    # sale.order + tmf.product.order (TMF622)
        "tmf_service_order",       # tmf.service.order (TMF641)
        "tmf_resource_order",      # tmf.resource.order (TMF652)
        "tmf_product_inventory",   # tmf.product (TMF637)
        "tmf_service_inventory",   # tmf.service (TMF638)
        "tmf_resource_inventory",  # stock.lot resource (TMF639)
        "tmf_product_catalog",     # product offering/spec refs
        "tmf_process_flow",        # TMF701 processFlow/taskFlow
    ],
    "installable": True,
    "license": "LGPL-3",
}
```

#### `tmfc003_wiring/models/wiring.py`

Three mixin extensions with the standard `_resolve_tmf_refs` / `skip_tmf_wiring` pattern:

**`SaleOrderTMFC003Wiring` (inherits `sale.order`):**
- Add `service_order_ids = Many2many("tmf.service.order", ...)` — the downstream service orders for this product order
- Add `product_order_process_flow_ids = Many2many("tmf.process.flow", ...)` — delivery process flows
- Add `delivery_state = Char(...)` — orchestration-level delivery tracking state
- Override `write()` — when `tmf_status` transitions to `inProgress`, trigger `_spawn_service_orders()`
- Add `_spawn_service_orders()` — creates `tmf.service.order` records from product order items, resolving product spec → service spec chain
- Add `_notify_delivery_state_change()` — publishes `ProductOrderStateChangeEvent` when delivery state is driven by service/resource layer
- Override `create()` — hook `_resolve_tmf_refs()` as per pattern

**`ServiceOrderTMFC003Wiring` (inherits `tmf.service.order`):**
- Add `product_order_id = Many2one("sale.order", ...)` — the originating product order
- Add `resource_order_ids = Many2many("tmf.resource.order", ...)` — downstream resource orders
- Add `_spawn_resource_orders()` — creates `tmf.resource.order` records from service order items, resolving service spec → resource spec chain
- Override `write()` — when `state` transitions to `completed`/`failed`, call `_propagate_state_to_product_order()`
- Add `_propagate_state_to_product_order()` — all service orders for a product order completed → advance product order state; any failed → set product order to `failed`

**`ResourceOrderTMFC003Wiring` (inherits `tmf.resource.order`):**
- Add `service_order_id = Many2one("tmf.service.order", ...)` — the originating service order
- Override `write()` — when `state` transitions to `completed`/`failed`, call `_propagate_state_to_service_order()`
- Add `_propagate_state_to_service_order()` — all resource orders for a service order completed → advance service order; any failed → fail service order

**`TMFC003WiringTools` (AbstractModel `tmfc003.wiring.tools`):**
- `_extract_event_resource(payload)` — standard helper
- `_extract_resource_id(payload)` — standard helper
- `_reconcile_service_order_state_change(payload)` — handle incoming `ServiceOrderStateChangeEvent` from TMF641
- `_reconcile_resource_order_state_change(payload)` — handle incoming `ResourceOrderStateChangeEvent` from TMF652
- `_provision_delivery_process_flow(sale_order)` — creates a TMF701 `tmf.process.flow` for a product order delivery, with task flows for each fulfillment step
- `_update_product_inventory_on_completion(sale_order)` — when a product order completes, update `tmf.product` records

#### `tmfc003_wiring/controllers/controllers.py`

```python
BASE_LISTENER = "/tmfc003/listener"

# Route: POST /tmfc003/listener/serviceOrder
# Handles: ServiceOrderStateChangeEvent, ServiceOrderCreateEvent, ServiceOrderAttributeValueChangeEvent, ServiceOrderDeleteEvent
# Dispatches to: tmfc003.wiring.tools._reconcile_service_order_state_change

# Route: POST /tmfc003/listener/resourceOrder
# Handles: ResourceOrderStateChangeEvent, ResourceOrderCreateEvent, ResourceOrderAttributeValueChangeEvent, ResourceOrderDeleteEvent
# Dispatches to: tmfc003.wiring.tools._reconcile_resource_order_state_change

# Route: GET+POST /tmfc003/hub
# Hub registration endpoint for TMFC003 outbound TMF622/701 subscriptions
```

### 4.3 Files to Modify

| File | Change Needed | Justification |
|------|---------------|---------------|
| `tmf_service_order/models/main_model.py` | Add `_notify` stateChange specialization | TMFC003 depends on explicit `ServiceOrderStateChangeEvent` |
| `tmf_service_order/models/main_model.py` | Add `product_order_ref_json` field (raw JSON) | Store incoming product order ref for resolution |
| `tmf_resource_order/models/main_model.py` | Add `_notify` stateChange specialization | TMFC003 depends on explicit `ResourceOrderStateChangeEvent` |
| `tmf_resource_order/models/main_model.py` | Add `service_order_ref_json` field (raw JSON) | Store incoming service order ref for resolution |
| `tmf_service_inventory/models/sale_order.py` | Deprecate auto-creation on `action_confirm` | Auto-creation bypasses TMFC003 orchestration; should be replaced by the TMFC003 wiring path |

> **Note:** Direct modifications to base modules (`tmf_service_order`, `tmf_resource_order`) should follow the inheritance pattern — extend in `tmfc003_wiring/models/wiring.py` using `_inherit`, not by editing the base module files. The column above lists which base models need fields/behaviors extended.

### 4.4 Implementation Sequence

```
Phase 1: Skeleton + Reference Fields
  1. Create tmfc003_wiring addon skeleton
  2. Add FK fields: sale.order.service_order_ids, tmf.service.order.product_order_id,
     tmf.service.order.resource_order_ids, tmf.resource.order.service_order_id
  3. Add raw JSON ref fields on service order and resource order

Phase 2: State Propagation Logic
  4. Implement _propagate_state_to_service_order() in ResourceOrderTMFC003Wiring
  5. Implement _propagate_state_to_product_order() in ServiceOrderTMFC003Wiring
  6. Wire write() hooks with skip_tmf_wiring guard

Phase 3: Orchestration Spawn Logic
  7. Implement _spawn_service_orders() on SaleOrderTMFC003Wiring
  8. Implement _spawn_resource_orders() on ServiceOrderTMFC003Wiring
  9. Decide: trigger on order confirmation OR on explicit TMFC003 orchestration call

Phase 4: Event Listener Routes
  10. Implement listener controller with /tmfc003/listener/serviceOrder route
  11. Implement listener controller with /tmfc003/listener/resourceOrder route
  12. Implement TMFC003WiringTools._reconcile_service_order_state_change()
  13. Implement TMFC003WiringTools._reconcile_resource_order_state_change()

Phase 5: Event Publication
  14. Verify TMF622 state-change events are published when orchestration drives state transitions
  15. Implement TMF701 process/task flow provisioning per product order delivery

Phase 6: Inventory Update
  16. Implement _update_product_inventory_on_completion() for TMF637 updates

Phase 7: Hub Registration
  17. Add hub routes for TMFC003 subscriptions (TMF641 + TMF652)
  18. Register TMFC003 listener routes with hub on install

Phase 8: Documentation
  19. Update TMFC_WIRING_CHECKLIST.md
  20. Update TMFC_IMPLEMENTATION_STATUS.md
```

---

## 5. Risk Assessment and Dependencies

### 5.1 External Dependencies (blocking)

| Dependency | Status | Risk | Mitigation |
|------------|--------|------|------------|
| `tmf_service_order` (TMF641 base) | ✅ Present | Medium — no `cancelServiceOrder`; `_notify` lacks stateChange | Extend via `_inherit`; add stateChange event in TMFC003 wiring |
| `tmf_resource_order` (TMF652 base) | ✅ Present | Medium — no `cancelResourceOrder`; `_notify` lacks stateChange | Extend via `_inherit`; add stateChange event in TMFC003 wiring |
| `tmf_service_inventory` (TMF638) | ✅ Present | **High** — auto-creates services on `action_confirm`, which conflicts with TMFC003's orchestrated approach | Must deactivate or refactor auto-creation before TMFC003 spawn logic runs |
| `tmf_resource_inventory` (TMF639) | ⚠️ Partial | Medium — stock.lot-based resource model, no ODA event publication | TMFC003 wiring can add event publication in its scope |
| `tmf_product_inventory` / TMFC005 | ✅ Fully wired | Low — TMFC005 manages `tmf.product` correctly | TMFC003 must update `tmf.product` via the established pattern, not bypass it |
| `tmf_process_flow` (TMF701) | ✅ Present | Low — already used by TMFC005 and TMFC027 | Reuse pattern; provision flows per order delivery |

### 5.2 Architectural Risks

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|------------|
| **Circular state propagation** | High | ResourceOrder → ServiceOrder → ProductOrder state updates could recurse if guards are absent | Use `skip_tmf_wiring` context flag on all propagation writes, consistent with existing pattern |
| **Race condition on parallel resource orders** | Medium | Multiple `tmf.resource.order` records completing asynchronously may trigger ServiceOrder completion multiple times | Implement idempotent "all complete?" check before advancing parent state |
| **Conflict with tmf_service_inventory auto-creation** | High | `sale_order.py` in `tmf_service_inventory` auto-creates `tmf.service` on confirm, bypassing TMFC003 | Must coordinate: either move auto-creation to TMFC003 wiring, or gate it behind a config flag |
| **Missing cancelServiceOrder/cancelResourceOrder** | Medium | Cancellation flow is not modeled; TMFC003 needs to propagate cancellation down the chain | Create cancellation models in TMFC003 wiring (or note as a known gap for TMFC007/TMFC011) |
| **TMF622 stateChange double-publication** | Medium | TMFC002 already publishes ProductOrderStateChangeEvent from `sale.order` write(); TMFC003 would also publish it from orchestration callbacks — risk of duplicate events | Coordinate: TMFC003 should update state via a TMFC003-context write that suppresses TMFC002's hook OR publish from a dedicated TMFC003 notification path |
| **Product spec → service spec resolution** | Medium | Resolving which service specs to fulfill requires `product.template.service_specification_ids` (from TMFC001 wiring) to be populated | Dependency on TMFC001 wiring being fully operational; document as prerequisite |
| **Hub registration on install** | Low | TMFC003 listener routes must be registered with the hub after install | Follow TMFC005/TMFC027 pattern: use `post_init_hook` or documented manual hub registration step |

### 5.3 Dependency Graph

```
TMFC003 wiring depends on:
  tmf_product_ordering     (TMF622 — sale.order)    ← TMFC002 wired ✅
  tmf_service_order        (TMF641 — tmf.service.order)  ← base present, not wired
  tmf_resource_order       (TMF652 — tmf.resource.order) ← base present, not wired
  tmf_product_inventory    (TMF637 — tmf.product)        ← TMFC005 wired ✅
  tmf_service_inventory    (TMF638 — tmf.service)        ← base present, not wired
  tmf_resource_inventory   (TMF639 — stock.lot)          ← base present, not wired
  tmf_product_catalog      (TMF620 — product spec chain) ← TMFC001 wired ✅
  tmf_process_flow         (TMF701 — process/task flow)  ← present, used by others ✅

TMFC003 is a prerequisite for:
  TMFC007 ServiceOrderManagement (needs TMFC003 orchestration context)
  TMFC011 ResourceOrderManagement (needs TMFC003 orchestration context)
  TMFC008 ServiceInventory (delivery completion drives service inventory)
  TMFC012 ResourceInventory (delivery completion drives resource inventory)
```

---

## 6. Estimated Complexity Relative to TMFC005

### 6.1 TMFC005 Wiring Profile (baseline)

TMFC005 (`tmfc005_wiring`) is the reference complexity benchmark:
- **Models extended:** 1 primary (`tmf.product`)
- **Reference types resolved:** ~10 FK links (product spec, offering, price, party, resource, service, agreement, billing account, geography ×3)
- **Published events:** 5 event types (create, update, stateChange, delete, batch)
- **Subscribed events (listener routes):** 5 delete events from upstream components
- **Process flow integration:** Yes (provisions TMF701 flows per product item)
- **Cross-component dependencies:** 10 TMF IDs
- **Complexity tier:** Moderate

### 6.2 TMFC003 Complexity Estimate

| Dimension | TMFC005 | TMFC003 | Ratio |
|-----------|---------|---------|-------|
| Models extended | 1 | 3 (`sale.order`, `tmf.service.order`, `tmf.resource.order`) | 3× |
| Reference types / FK links | ~10 | ~8 (order chain links are fewer but deeper) | 0.8× |
| Published events | 5 | ~8 (TMF622 stateChange/info + TMF701 create/state/delete ×2) | 1.6× |
| Subscribed event listener routes | 5 | 2 primary (TMF641 + TMF652) but each may handle 4 event subtypes | ~1.5× |
| State propagation logic | None | 3-layer cascade: resource → service → product order | ∞ (new category) |
| Spawn/orchestration logic | None | 2 spawn paths (product→service, service→resource) | ∞ (new category) |
| Cross-cutting conflict risks | Low | High (tmf_service_inventory conflict, double-publish risk) | ↑ |
| Integration surface | 10 TMF IDs | 10 TMF IDs | ~1× |

### 6.3 Complexity Verdict

**TMFC003 is approximately 2–3× more complex than TMFC005** due to:

1. **Three models must be extended** (not one).
2. **State propagation cascade** — TMFC003 introduces a novel pattern (multi-layer state machine propagation) not present in any other wiring addon. This is the highest-risk and most design-intensive part.
3. **Spawn orchestration logic** — product spec → service spec → resource spec resolution requires cross-catalog traversal.
4. **Conflict resolution** with existing `tmf_service_inventory` auto-creation.
5. **Double-publication coordination** with TMFC002's existing TMF622 hooks.

TMFC003 is the **most architecturally significant** of the Sprint 2 components. It is the backbone that makes product-to-service-to-resource fulfillment coherent. Getting it wrong would create technical debt across TMFC007, TMFC008, TMFC011, and TMFC012.

### 6.4 Estimated Effort

| Phase | Estimate |
|-------|----------|
| Phase 1 (Skeleton + FKs) | 0.5 days |
| Phase 2 (State propagation) | 1.5 days |
| Phase 3 (Spawn orchestration) | 2 days |
| Phase 4 (Event listener routes) | 1 day |
| Phase 5 (Event publication) | 0.5 days |
| Phase 6 (Inventory update) | 0.5 days |
| Phase 7 (Hub registration) | 0.5 days |
| Phase 8 (Docs + checklist update) | 0.5 days |
| **Total** | **~7 development days** |

Compare: TMFC005 wiring was approximately 2–3 development days. TMFC003 at ~7 days is consistent with the 2–3× complexity estimate.

---

## 7. Key Design Decisions Required Before Implementation

The following architectural decisions should be made before implementation begins:

1. **Orchestration trigger point:** Should TMFC003 spawn service orders automatically on `sale.order` confirmation, or only when explicitly triggered (e.g., by a TMF622 `inProgress` state transition)? The explicit trigger approach is safer and more aligned with ODA orchestration intent.

2. **`tmf_service_inventory` conflict:** Should `sale_order.py` auto-creation be replaced by TMFC003's orchestration path, or made conditional via a feature flag? Replacing it is architecturally cleaner; a feature flag reduces migration risk.

3. **State aggregation semantics:** When some service orders are complete and others are still in progress for the same product order, what is the product order's state? Suggest: `partial` until all complete → `completed`.

4. **TMF622 double-publication:** Should TMFC003 suppress TMFC002's `ProductOrderStateChangeEvent` during orchestration-driven state transitions, or publish an additional event? The cleanest pattern is: TMFC003 uses `skip_tmf_wiring` context on its writes, then explicitly publishes via its own notification path.

5. **Cross-catalog resolution depth:** Should TMFC003 resolve product spec → service spec → resource spec automatically at spawn time, or operate on pre-populated order items only? Automatic resolution is more powerful but requires TMFC001 wiring to be complete and populated.

---

## 8. Appendix: Checklist Template for Implementation Tracking

Once implementation begins, use this checklist in `TMFC_WIRING_CHECKLIST.md`:

```markdown
## TMFC003 – ProductOrderDeliveryOrchestrationAndManagement

**Status:** In analysis → In implementation
**Target sprint:** Sprint 2
**Expected addon:** `tmfc003_wiring`

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs/dependencies extracted from YAML
- [x] Analysis document created (docs/TMFC003_ANALYSIS.md)
- [ ] Design decisions resolved (see TMFC003_ANALYSIS.md §7)
- [ ] Addon skeleton created
- [ ] FK fields added to sale.order, tmf.service.order, tmf.resource.order
- [ ] State propagation cascade implemented (resource→service→product)
- [ ] Spawn orchestration logic implemented
- [ ] Event listener routes implemented for TMF641
- [ ] Event listener routes implemented for TMF652
- [ ] TMF622 state-change publication verified from orchestration paths
- [ ] TMF701 process/task flows provisioned per delivery
- [ ] tmf.product updated on delivery completion
- [ ] Hub registration verified
- [ ] tmf_service_inventory conflict resolved
- [ ] Verification notes captured
- [ ] TMFC_IMPLEMENTATION_STATUS.md updated
```

---

*Analysis complete. No code was written or modified in this session. 🏛️*
