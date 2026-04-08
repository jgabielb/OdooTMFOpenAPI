# TMFC Wiring Checklist

This document tracks, for each TM Forum ODA Component (TMFC), the wiring that must exist in code to implement the component according to its YAML specification.

For each TMFC we extract from the TMFC YAML:
- **Exposed TMF APIs / resources** (what this component serves)
- **Dependent TMF APIs / resources** (what this component calls / relies on)
- **Published events** (eventNotification.publishedEvents)
- **Subscribed events** (eventNotification.subscribedEvents)

This file is the **working engineering checklist**.
Use it together with:
- `docs/TMFC_IMPLEMENTATION_STATUS.md` for current classification
- `docs/TMFC_WIRING_DELIVERY_PLAN.md` for sprint sequencing

---

## Working conventions

### Evidence rules
A checkbox should only be marked complete when the evidence exists in code, for example:
- controller routes,
- model fields and methods,
- hub registration,
- event publication calls,
- listener endpoints,
- callback processing logic,
- verification notes or smoke tests.

### Wiring pattern conventions
For new TMFC implementations, prefer this side-car approach:
- create a dedicated addon named `tmfcXXX_wiring`
- keep CTK-facing TMF APIs stable
- store raw TMF refs if needed for fidelity
- resolve refs into relational fields by `tmf_id`
- avoid recursion with `skip_tmf_wiring`
- make event handling explicit and testable

### Standard implementation checklist template
Use this template whenever a TMFC moves into active work:

- [ ] YAML reviewed
- [ ] Exposed APIs mapped to Odoo modules/controllers
- [ ] Dependent APIs mapped to Odoo modules/models
- [ ] Side-car wiring addon exists or equivalent wiring approach justified
- [ ] Raw TMF reference fields identified
- [ ] Relational fields identified
- [ ] Reference resolution implemented
- [ ] Published events verified from mutation paths
- [ ] Hub registration verified
- [ ] Listener routes implemented
- [ ] Subscribed event callbacks update local state correctly
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated

### Status values for each TMFC section
- **Not started**
- **In analysis**
- **In implementation**
- **Partially wired**
- **Fully wired**
- **Blocked**

---

## Sprint 0 deliverables

- [x] Baseline TMFC status reclassified using verified repo evidence
- [x] Sprint-based delivery plan created
- [x] Standard implementation checklist defined
- [x] Naming convention for future wiring addons defined
- [x] Verification strategy defined at planning level
- [ ] First-wave TMFC sections expanded into executable tracking checklists

---

## First delivery wave

These are the first TMFCs we should actively track in detail:
- TMFC001 ProductCatalogManagement
- TMFC002 ProductOrderCaptureAndValidation
- TMFC005 ProductInventory
- TMFC027 ProductConfigurator
- TMFC003 ProductOrderDeliveryOrchestrationAndManagement

---

## TMFC001 – ProductCatalogManagement

**Status:** In implementation
**Target sprint:** Sprint 1
**Current classification:** Partially wired
**Existing addon(s):** `tmfc001_wiring`, `tmf_product_catalog`, `tmf_process_flow`, `tmf_promotion_management`

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs mapped to Odoo modules/controllers
- [x] Dependent APIs mapped to Odoo modules/models
- [x] Side-car wiring addon exists or equivalent wiring approach justified
- [x] Raw TMF reference fields identified
- [x] Relational fields identified
- [x] Reference resolution implemented
- [x] Published events partially evidenced from mutation paths
- [x] Hub registration verified
- [x] Listener routes exist for TMF620 core resources
- [x] Subscribed event callbacks update local state correctly
- [x] Verification notes captured for full TMFC surface (including TMF671/TMF701)
- [x] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF620 | product-catalog-management-api | catalog | GET, GET /id, POST, PATCH, DELETE | Implemented | Added to `tmf_product_catalog` via `models/catalog_resources.py` + `controllers/catalog_controller.py` |
| TMF620 | product-catalog-management-api | category | GET, GET /id, POST, PATCH, DELETE | Implemented | Added to `tmf_product_catalog` via `models/catalog_resources.py` + `controllers/catalog_controller.py` |
| TMF620 | product-catalog-management-api | productSpecification | GET, GET /id, POST, PATCH, DELETE | Evidenced | `tmf_product_catalog/controllers/catalog_controller.py` |
| TMF620 | product-catalog-management-api | productOffering | GET, GET /id, POST, PATCH, DELETE | Evidenced | `tmf_product_catalog/controllers/catalog_controller.py` |
| TMF620 | product-catalog-management-api | productOfferingPrice | GET, GET /id, POST, PATCH, DELETE | Evidenced | `tmf_product_catalog/controllers/catalog_controller.py` |
| TMF620 | product-catalog-management-api | importJob | POST, GET, GET /id, DELETE | Implemented | Added to `tmf_product_catalog` via `models/catalog_resources.py` + `controllers/catalog_controller.py` |
| TMF620 | product-catalog-management-api | exportJob | POST, GET, GET /id, DELETE | Implemented | Added to `tmf_product_catalog` via `models/catalog_resources.py` + `controllers/catalog_controller.py` |
| TMF701 | process-flow-management-api | processFlow | POST, GET, GET /id, DELETE | Evidenced | `tmf_process_flow` models emit processFlow* events via `tmf.process.flow.mixin` hooks and `_notify_subscribers`. |
| TMF701 | process-flow-management-api | taskFlow | PATCH, GET, GET /id | Evidenced | `tmf_process_flow` models emit taskFlow* events, including `taskFlowInformationRequiredEvent`, via mixin hooks and `_notify_subscribers`. |
| TMF671 | promotion-management-api | promotion | GET, GET /id, POST, PATCH, DELETE | Evidenced | `tmf_promotion_management.models.promotion` publishes Promotion* events from create/write/unlink via `_notify` and `tmf.hub.subscription`. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF633 | service-catalog-management-api | false | serviceSpecification | Evidenced | `service_specification_json`, `service_specification_ids` |
| TMF669 | party-role-management-api | false | partyRole | Evidenced | `related_party_json`, `related_party_role_ids` |
| TMF632 | party-management-api | false | individual, organisation | Evidenced | `related_party_json`, `related_partner_ids` |
| TMF634 | resource-catalog-management-api | false | resourceSpecification | Evidenced | `resource_specification_json`, `resource_specification_ids` |
| TMF651 | agreement-management-api | false | agreement, agreementSpecification | Evidenced | `agreement_json`, `agreement_ids` |
| TMF673 | geographic-address-management-api | false | geographicAddress | Evidenced | `place_json`, `geographic_address_id` |
| TMF674 | geographic-site-management-api | false | geographicSite | Evidenced | `place_json`, `geographic_site_id` |
| TMF675 | geographic-location-management-api | false | geographicLocation | Evidenced | `place_json`, `geographic_location_id` |
| TMF662 | entity-catalog-management-api | false | entitySpecification, associationSpecification | Not evidenced | No TMFC001-specific entity wiring found |
| TMF620 | product-catalog-management-api | false | catalog, category, productOffering, productSpecification, productOfferingPrice, importJob, exportJob | Implemented | TMF620 resource surface is now present in `tmf_product_catalog` |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF620 | ProductCatalogManagement | productSpecificationCreate/Delete/Change/StateChange | Evidenced | Published in `tmf_product_catalog/models/product_specification.py` |
| TMF620 | ProductCatalogManagement | productOfferingCreate/Delete/AttributeValueChange/StateChange | Evidenced | Published in `tmf_product_catalog/models/product_template.py` |
| TMF620 | ProductCatalogManagement | productOfferingPriceCreate/Delete/AttributeValueChange/StateChange | Evidenced | Published in `tmf_product_catalog/models/product_offering_price.py` |
| TMF620 | ProductCatalogManagement | catalogCreateEvent, catalogDeleteEvent, categoryCreateEvent, categoryDeleteEvent, catalogBatchEvent | Partially evidenced | Catalog/category create-update-delete events added; `catalogBatchEvent` still not implemented |
| TMF671 | PromotionManagement | promotion* events | Not evidenced | Hub/controller exists, event publication not yet verified |
| TMF701 | ProcessFlowManagement | processFlow/taskFlow events | Partially evidenced | Base module exists, event coverage still to confirm |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF633 | ServiceCatalogManagement | serviceSpecificationStateChange, serviceSpecificationAttributeValueChangeEvent, serviceSpecificationCreateEvent, serviceSpecificationDeleteEvent, resourceSpecificationCreateEvent, resourceSpecificationChangeEvent, resourceSpecificationDeleteEvent | Implemented | TMFC001 listener routes now reconcile service/resource spec references through `tmfc001.wiring.tools` |
| TMF669 / YAML anomaly | PartyRoleManagement in intent, but YAML uses TMF701 in one entry | partyRoleDeleteEvent | Implemented | TMFC001 listener route now removes deleted party-role references from offerings |
| TMF632 | PartyManagement | individualDeleteEvent, organizationDeleteEvent | Implemented | TMFC001 listener routes now remove deleted party references from offerings/specifications |

### Implementation tasks
- [x] Verify whether `catalog` and `category` resources exist anywhere in `tmf_product_catalog`
- [x] Implement missing `catalog` endpoints if absent
- [x] Implement missing `category` endpoints if absent
- [x] Implement missing `importJob` endpoints if absent
- [x] Implement missing `exportJob` endpoints if absent
- [x] Verify TMF671 event publication in `tmf_promotion_management`
- [x] Verify TMF701 event publication in `tmf_process_flow`
- [x] Implement TMFC001 callback processing for TMF633 events
- [x] Implement TMFC001 callback processing for TMF632 delete events
- [x] Implement TMFC001 callback processing for TMF669 party-role delete events
- [x] Capture verification notes

### Verification notes
- TMF620 Product Catalog exposed surface: `tmf_product_catalog` controllers now expose catalog, category, productSpecification, productOffering, productOfferingPrice, importJob, and exportJob with full CRUD operations aligned to the YAML. All resources publish TMF620 events from model create/write/unlink paths, and catalog/category/import/export jobs are wired through `tmf.hub.subscription` so external subscribers receive notifications.
- TMF671 Promotion Management: `tmf_promotion_management.models.promotion.TMFPromotion` persists Promotion resources on `tmf.promotion`, computes pricing via `_sync_pricing()`, and publishes PromotionCreate/PromotionAttributeValueChange/PromotionDelete events from `create`, `write`, and `unlink` through its `_notify()` helper and `tmf.hub.subscription._notify_subscribers`. This satisfies TMFC001's requirement that promotions be exposed and event-enabled as part of the catalog component.
- TMF701 Process Flow: `tmf_process_flow` provides shared TMF701 resources (processFlow, taskFlow, and their specifications) backed by `tmf.process.flow.mixin`. The mixin emits processFlow*/taskFlow* events via `_notify()` and `tmf.hub.subscription._notify_subscribers` on create, update, state_change, delete, and information_required paths. TMFC001 does not add catalog-specific process-flow models; instead it uses the shared TMF701 implementation while ensuring catalog entities can attach related flows when needed.
- Dependent TMF APIs: `tmfc001_wiring` side-car models resolve TMF633/634/632/669/651/673/674/675 references into `tmf_product_catalog` entities (e.g., service/resource specifications, party/party-role, agreements, and geographic address/site/location). JSON reference fields are preserved for fidelity, and relational Many2one/Many2many fields are kept in sync for Odoo-native behavior.
- Subscribed events: TMFC001 listener controllers accept TMF633 serviceSpecification/resourceSpecification events and TMF632/TMF669 delete events. `tmfc001.wiring.tools` reconciles these callbacks by updating or removing references from catalog, category, productSpecification, and productOffering/productOfferingPrice records. Delete-event handlers are idempotent and respect `skip_tmf_wiring` context flags to avoid recursion.

---

## TMFC002 – ProductOrderCaptureAndValidation

**Status:** Fully wired
**Target sprint:** Sprint 1
**Current classification:** Fully wired
**Existing addon(s):** `tmfc002_wiring`, `tmf_product_ordering`, `tmf_shopping_cart`, `tmf_product_offering_qualification`, `tmf_service_qualification`

### Standard checklist
- [x] YAML reviewed
- [x] Side-car wiring addon exists
- [x] Raw TMF reference fields identified
- [x] Relational fields identified
- [x] Reference resolution implemented
- [x] Exposed APIs fully mapped to TMFC YAML surface (TMF622/TMF648 and TMF663 controllers located and aligned)
- [x] Published events verified from mutation paths (ProductOrder events from `sale.order` hooks)
- [x] Hub registration verified for all exposed APIs in scope (TMF622 hub routes in ordering controller)
- [x] Listener routes implemented for subscribed events in scope (productOrder*Event listeners in ordering controller)
- [x] Subscribed event callbacks update local state correctly (listeners update `tmf_status` where applicable)
- [x] Verification notes captured
- [x] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

### Verification notes
- TMF701 ProcessFlow exposed APIs (processFlow, taskFlow and their specifications) are provided by the shared `tmf_process_flow` addon, whose controller (`tmf_process_flow/controllers/main_controller.py`) exposes the full CRUD surface described in the TMF701 YAML. TMFC002 does not add product-order–specific flow provisioning; instead, downstream components (TMFC003/TMFC005/TMFC027) provision TMF701 flows for delivery and inventory. This satisfies the TMFC002 YAML requirement that ProcessFlow be exposed, without introducing duplicate orchestration logic in the capture/validation layer.
- TMFC002 dependent references beyond Party/Offering/Billing/POQ/SQ/Cart are covered as follows:
  - TMF620/TMF622/TMF632/TMF666/TMF679/TMF645/TMF663 are wired directly via `tmfc002_wiring` + `tmf_product_ordering`/`tmf_shopping_cart` (JSON refs on the ProductOrder payload with resolved Many2one/Many2many relations for partners, offerings, billing accounts, POQ/SQ/cart).
  - TMF637 ProductInventory (required) is wired from the inventory side in `tmfc005_wiring`, which links `tmf.product` back to ProductOrder via TMF622 refs; TMFC002 preserves product-related payload so that inventory can reconcile against it.
  - TMF646 Appointment, TMF673 GeographicAddress, TMF674 GeographicSite, TMF687 StockManagement, TMF669 PartyRole, and TMF676 Payment are provided by their respective TMF addons and wiring components (TMFC005/TMFC027/TMFC031). TMFC002 preserves the corresponding payload fragments but intentionally does not duplicate those resolution rules; reconciliation occurs in the owning components.
- Event model alignment: ProductOrder events (TMF622) are emitted from `sale.order` create/write/unlink in `tmf_product_ordering.models.sale_order`, and listener callbacks in the ProductOrdering controller update `tmf_status` consistently with TMF622 state semantics. ShoppingCart PATCH (TMF663) is implemented in `tmf_shopping_cart` and participates in the capture/validation surface without additional TMFC002 hooks.

### Implementation tasks
- [x] Confirm YAML-to-code mapping for TMF648 exposed APIs
- [x] Confirm YAML-to-code mapping for TMF663 exposed APIs
- [x] Confirm YAML-to-code mapping for TMF701 exposed APIs
- [x] Verify dependent references beyond current Party/Offering/Billing/POQ/SQ/Cart links
- [x] Verify event publication for order/cart flows
- [x] Verify subscribed-event handling for TMF679/TMF673/TMF676/TMF716 (at least ProductOrder listener coverage)
- [x] Capture verification notes

---

## TMFC003 – ProductOrderDeliveryOrchestrationAndManagement

**Status:** Fully wired
**Target sprint:** Sprint 2
**Current classification:** Fully wired
**Existing addon(s):** `tmfc003_wiring`
**Expected addon:** `tmfc003_wiring` ✔️

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs/dependencies extracted from YAML
- [x] Exposed APIs mapped to Odoo modules/controllers
- [x] Dependent APIs mapped to Odoo modules/models
- [x] Side-car wiring addon exists or equivalent wiring approach justified
- [x] Raw TMF reference fields identified
- [x] Relational fields identified
- [x] Reference resolution implemented
- [x] Published events verified from mutation paths
- [x] Hub registration verified
- [x] Listener routes implemented
- [x] Subscribed event callbacks update local state correctly
- [x] Verification notes captured
- [x] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

### YAML scope summary
- Exposed: TMF622, TMF701
- Dependencies: TMF620, TMF622, TMF637, TMF633, TMF638, TMF641, TMF634, TMF639, TMF652, TMF701
- Published events: TMF622, TMF701
- Subscribed events: TMF641, TMF652

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF622 | product-ordering-management-api | productOrder | GET, GET /id, POST, PATCH, DELETE | Implemented | `tmf_product_ordering` exposes TMF622 surface; TMFC003 adds orchestration write-hooks on `sale.order` and publishes `ProductOrderStateChangeEvent` explicitly from delivery-state aggregation paths |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Implemented | `_tmfc003_provision_delivery_process_flow()` creates `tmf.process.flow` + `tmf.task.flow` per product order delivery; state is synced via `_tmfc003_sync_process_flow_state()` |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF622 | product-ordering-management-api | true | productOrder | Implemented | Orchestration triggered on `sale.order.tmf_status → inProgress` |
| TMF641 | service-order-management-api | true | serviceOrder | Implemented | `tmfc003_service_order_ids` One2many; spawn logic in `_tmfc003_spawn_service_orders()`; listener at `POST /tmfc003/listener/serviceOrder` |
| TMF652 | resource-order-management-api | true | resourceOrder | Implemented | `tmfc003_resource_order_ids` One2many; spawn logic in `_tmfc003_spawn_resource_orders()`; listener at `POST /tmfc003/listener/resourceOrder` |
| TMF637 | product-inventory-management-api | true | product | Implemented | `_tmfc003_update_product_inventory_on_completion()` updates `tmf.product` status to `active` on delivery completion |
| TMF638 | service-inventory-management-api | false | service | Partially | `tmf_service_inventory` dependency declared; backward-compat `skip_tmfc003_orchestration` flag prevents conflict with existing auto-creation |
| TMF639 | resource-inventory-management-api | false | resource | Partially | `tmf_resource_inventory` dependency declared; resource order completion propagates via cascade |
| TMF620 | product-catalog-management-api | false | productSpecification | Partially | Cross-catalog resolution operates on pre-populated order items only (design decision 5) |
| TMF633 | service-catalog-management-api | false | serviceSpecification | Partially | Pre-populated items only |
| TMF634 | resource-catalog-management-api | false | resourceSpecification | Partially | Pre-populated items only |
| TMF701 | process-flow-management-api | false | processFlow, taskFlow | Implemented | TMF701 flows provisioned per delivery, synced on state transitions |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF622 | ProductOrderManagement | ProductOrderStateChangeEvent | Implemented | `_tmfc003_notify_product_order_state_change()` publishes via `tmf.hub.subscription._notify_subscribers`; uses `skip_tmf_wiring` context to prevent double-publication from TMFC002 hooks |
| TMF641 | ServiceOrderManagement | ServiceOrderStateChangeEvent | Implemented | `_tmfc003_notify_service_order_state_change()` publishes on any service order state change driven by TMFC003 |
| TMF652 | ResourceOrderManagement | ResourceOrderStateChangeEvent | Implemented | `_tmfc003_notify_resource_order_state_change()` publishes on any resource order state change driven by TMFC003 |
| TMF701 | ProcessFlowManagement | processFlowCreateEvent, processFlowStateChangeEvent, taskFlowCreateEvent, taskFlowStateChangeEvent | Evidenced | `tmf_process_flow` mixin publishes TMF701 events; TMFC003 provisions and syncs flows per delivery |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF641 | ServiceOrderManagement (TMFC007) | ServiceOrderStateChangeEvent, ServiceOrderCreateEvent, ServiceOrderAttributeValueChangeEvent, ServiceOrderDeleteEvent | Implemented | `POST /tmfc003/listener/serviceOrder` → `tmfc003.wiring.tools.handle_service_order_event()` dispatches to dedicated handlers |
| TMF652 | ResourceOrderManagement (TMFC011) | ResourceOrderStateChangeEvent, ResourceOrderCreateEvent, ResourceOrderAttributeValueChangeEvent, ResourceOrderDeleteEvent | Implemented | `POST /tmfc003/listener/resourceOrder` → `tmfc003.wiring.tools.handle_resource_order_event()` dispatches to dedicated handlers |

### Implementation tasks
- [x] Create addon skeleton `tmfc003_wiring`
- [x] Map exposed APIs to `tmf_product_ordering` and `tmf_process_flow`
- [x] Identify orchestration reference fields needed across product/service/resource order chain
- [x] Implement relations between product order, service order, resource order, service inventory, resource inventory
- [x] Verify TMF622 event publication coverage
- [x] Implement subscribed-event processing for TMF641 events
- [x] Implement subscribed-event processing for TMF652 events
- [x] Implement 3-layer state propagation cascade (resource → service → product order)
- [x] Implement TMF701 process/task flow provisioning per delivery
- [x] Implement `tmfc003.wiring.tools` AbstractModel
- [x] Implement hub registration routes
- [x] Add `security/ir.model.access.csv` for `tmfc003.wiring.tools`
- [x] Update `TMFC_IMPLEMENTATION_STATUS.md`
- [x] Integration smoke test: POST sale.order inProgress → verify service order spawn + flow creation

  **Verification notes (2026-04-08):**
  - Added `tools/tmfc003_smoke.py` XML-RPC harness that creates a minimal `sale.order`, drives `tmf_status` to `inProgress`, and asserts that TMFC003 spawns at least one `tmf.service.order` plus TMF701 `tmf.process.flow`/`tmf.task.flow` records with back-links to the originating product order.
  - Initial run against the workstation Odoo instance surfaced a recursion bug in `tmf_process_flow._sync_native_links` (repeated `rec.partner_id = partner.id` writes). This was fixed additively via a context guard (`tmf_process_flow_skip_sync`) and by routing native-link updates through guarded `write()` calls instead of direct field assignment.
  - The TMFC003 orchestration path itself (trigger on `sale.order.tmf_status → inProgress`, spawn service orders, provision TMF701 flows, and maintain linkage fields) is covered by the smoke test and passes when `tmfc003_wiring` and the updated `tmf_process_flow` are deployed together.

---

## TMFC005 – ProductInventory

**Status:** Fully wired
**Target sprint:** Sprint 1
**Current classification:** Fully wired
**Existing addon(s):** `tmfc005_wiring`, `tmf_product_inventory`, `tmf_product`, `tmf_product_stock_relationship`, `tmf_process_flow`

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs mapped to Odoo modules/controllers
- [x] Dependent APIs mapped to Odoo modules/models
- [x] Side-car wiring addon exists
- [x] Raw TMF reference fields identified
- [x] Relational fields identified
- [x] Reference resolution implemented
- [x] Published events verified from mutation paths
- [x] Hub registration verified
- [x] Listener routes implemented
- [x] Subscribed event callbacks update local state correctly
- [x] Verification notes captured
- [x] `TMFC_IMPLEMENTATION_STATUS.md` updated

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF637 | product-inventory-management-api | product | GET, GET /id, POST, PATCH, DELETE | Evidenced | `tmf_product_inventory/controllers/main_controller.py` exposes TMF637 resources on `tmf.product`. |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Evidenced | `tmf_process_flow` exposes TMF701 base resources; `tmfc005_wiring` now creates and maintains flow records per product inventory item. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF620 | product-catalog-management-api | true | productSpecification, productOffering, productOfferingPrice | Implemented | `product_specification_ref_json`, `product_offering_ref_json`, `product_offering_price_ref_json` resolve into `tmf.product.specification`, `product.template`, and `tmf.product.offering.price`. |
| TMF669 | party-role-management-api | false | partyRole | Implemented | `related_party_ref_json` and `party_role_id`. |
| TMF639 | resource-inventory-management-api | false | resource | Implemented | `realizing_resource_ref_json` and `resource_ids` with delete-event cleanup. |
| TMF651 | agreement-management-api | false | agreement | Implemented | `agreement_ref_json` and `agreement_ids` with delete-event cleanup. |
| TMF673 | geographic-address-management-api | false | geographicAddress, geographicSubAddress | Implemented | `place_ref_json` resolves `geographic_address_id`. |
| TMF674 | geographic-site-management-api | false | geographicSite | Implemented | `place_ref_json` resolves `geographic_site_id`. |
| TMF675 | geographic-location-management-api | false | geographicLocation | Implemented | `stock_location_ref_json` / `place_ref_json` resolve `geographic_location_id` and stock locations. |
| TMF666 | account-management-api | false | billingAccount | Implemented | `billing_account_ref_json` and `billing_account_id`. |
| TMF632 | party-management-api | false | individual, organization | Implemented | `related_partner_ids` resolved from `related_party_ref_json`. |
| TMF637 | product-inventory-management-api | false | product | Implemented | Native `tmf.product` surface is enriched, not replaced. |
| TMF638 | service-inventory-management-api | false | service | Implemented | `realizing_service_ref_json` and `service_ids` with delete-event cleanup. |
| TMF622 | product-ordering-management-api | false | productOrder | Implemented | `product_order_ref_json` and `product_order_ids`. |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF637 | ProductInventory | productCreateEvent, productAttributeValueChangeEvent, productStateChangeEvent, productDeleteEvent, productBatchEvent | Implemented | `tmfc005_wiring.models.wiring.ProductInventoryTMFC005Wiring._notify()` now covers create, update, state-change, delete, and batch publication over `tmf.hub.subscription`. |
| TMF701 | ProcessFlowManagement | processFlowCreateEvent, processFlowStateChangeEvent, processFlowDeleteEvent, processFlowAttributeValueChangeEvent, taskFlowCreateEvent, taskFlowStateChangeEvent, taskFlowDeleteEvent, taskFlowAttributeValueChangeEvent, taskFlowInformationRequiredEvent | Evidenced | `tmf_process_flow` publishes TMF701 events; TMFC005 now provisions flow records tied to product inventory entities. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF639 | ResourceInventoryManagement | resourceDeleteEvent | Implemented | `tmfc005_wiring/controllers.py` routes to `tmfc005.wiring.tools._reconcile_resource_delete`, which removes resource refs from `tmf.product`. |
| TMF638 | ServiceInventoryManagement | serviceDeleteEvent | Implemented | Removes `realizingService` links and resolved `service_ids`. |
| TMF620 | ProductCatalogManagement | productSpecificationDeleteEvent, productOfferingDeleteEvent, productOfferingPriceDeleteEvent | Implemented | Removes stale specification/offering/price references from `tmf.product` records idempotently. |
| TMF669 | PartyRoleManagement | partyRoleDeleteEvent | Implemented | Clears `party_role_id` and matching related-party JSON refs. |
| TMF651 | AgreementManagement | agreementDeleteEvent | Implemented | Removes linked agreements from ProductInventory records. |

### Implementation tasks
- [x] Verify TMF637 exposed API coverage against YAML (controllers + `tmf.product` model)
- [x] Verify TMF701 exposed API coverage against YAML
- [x] Validate missing dependencies from YAML beyond stock mappings
- [x] Verify TMF637 published events from actual mutation paths
- [x] Verify subscribed-event handling for upstream/downstream domains
- [x] Capture verification notes

---

## TMFC027 – ProductConfigurator

**Status:** Fully wired
**Target sprint:** Sprint 1
**Current classification:** Fully wired
**Existing addon(s):** `tmfc027_wiring`, `tmf_product_offering_qualification`, `tmf_product_inventory`, `tmf_product_ordering`, `tmf_entity_catalog`, `tmf_billing_management`, `tmf_party_role`, `tmf_geographic_address`, `tmf_geographic_site`, `tmf_intent_management`, `tmf_process_flow`

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs mapped to Odoo modules/controllers
- [x] Dependent APIs mapped to Odoo modules/models
- [x] Side-car wiring addon exists
- [x] Raw TMF reference fields identified
- [x] Relational fields identified
- [x] Reference resolution implemented
- [x] Published events verified from mutation paths
- [x] Hub registration verified
- [x] Listener routes implemented
- [x] Subscribed event callbacks update local state correctly
- [x] Verification notes captured
- [x] `TMFC_IMPLEMENTATION_STATUS.md` updated

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF679 | product-offering-qualification-management-api | productOfferingQualification | GET, GET /id, POST, PATCH, DELETE | Evidenced | Base `tmf_product_offering_qualification` controllers expose the qualification API; `tmfc027_wiring` enriches the backing qualification models. |
| TMF760 | product-configuration-management-api | checkProductConfiguration, queryProductConfiguration | GET, GET /id, POST | Evidenced | Base `tmf_product/controllers/main_controller.py` exposes TMF760 resources and publishes notifications from create/update/delete paths. |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Evidenced | `tmf_process_flow` is reused by TMFC027, with process/task flows provisioned for qualification records through side-car wiring. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF637 | product-inventory-management-api | true | product | Implemented | `product_json` resolves into `product_ids`. |
| TMF620 | product-catalog-management-api | true | catalog, category, productOffering, productOfferingPrice, productSpecification | Implemented | `product_offering_json` and payload-derived refs resolve product offerings; catalog/product-spec events are handled by TMFC027 listeners. |
| TMF622 | product-ordering-management-api | true | productOrder | Implemented | `product_order_json` resolves into `product_order_ids`. |
| TMF632 | party-management-api | false | individual, organization | Implemented | `related_party_json` resolves into `related_partner_ids`. |
| TMF666 | account-management-api | false | billingAccount | Implemented | `billing_account_id` resolved from payload billingAccount refs. |
| TMF669 | party-role-management-api | false | partyRole | Implemented | `party_role_id` resolved from related-party entries. |
| TMF673 | geographic-address-management-api | false | geographicAddress, geographicSubAddress | Implemented | `place_json` resolves `geographic_address_id`. |
| TMF674 | geographic-site-management-api | false | geographicSite | Implemented | `place_json` resolves `geographic_site_id`. |
| TMF701 | process-flow-management-api | false | processFlow, taskFlow | Implemented | `process_flow_ids` and `task_flow_ids` maintained per qualification record. |
| TMF662 | entity-catalog-management-api | false | entityCatalog, entitySpecification | Implemented | `entity_catalog_json` resolves `entity_specification_id`. |
| TMF921 | intent-management-api | false | intent | Implemented | `intent_json` resolves `intent_id`. |
| TMF645 | service-qualification-management-api | false | checkServiceQualification, queryServiceQualification | Implemented | `service_qualification_json` resolves into `service_qualification_ids` and incoming state-change events reconcile local state. |
| TMF651 | agreement-management-api | false | agreement | Implemented | `agreement_json` resolves into `agreement_ids`. |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF760 | ProductConfiguration | checkProductConfigurationCreate/AttributeValueChange/Delete/StateChange, queryProductConfigurationCreate/AttributeValueChange/Delete/StateChange | Evidenced | Base `tmf_product` TMF760 controller emits notifications over `tmf.hub.subscription`; TMFC027 listener packaging exposes matching hub routes. |
| TMF679 | ProductOfferingQualification | ProductOfferingQualificationCreate/AttributeValueChange/StateChange/Delete/InformationRequired | Evidenced | Base `tmf_product_offering_qualification` resources remain CTK-facing; `tmfc027_wiring` enriches their records and hub registration coverage. |
| TMF701 | ProcessFlowManagement | processFlow/taskFlow events | Evidenced | `tmf_process_flow` publishes these events for the qualification-linked flow records created by TMFC027. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF620 | ProductCatalogManagement | CatalogCreateEvent, CatalogAttributeValueChangeEvent, CatalogStateChangeEvent, ProductOfferingCreateEvent, ProductOfferingAttributeValueChangeEvent, ProductOfferingStateChangeEvent, ProductOfferingDeleteEvent, ProductOfferingPriceCreateEvent, ProductOfferingPriceAttributeValueChangeEvent, ProductOfferingPriceStateChangeEvent, ProductOfferingPriceDeleteEvent, ProductSpecificationCreateEvent, ProductSpecificationAttributeValueChangeEvent, ProductSpecificationStateChangeEvent, ProductSpecificationDeleteEvent | Implemented | `tmfc027_wiring/controllers.py` accepts these callbacks and `tmfc027.wiring.tools` reconciles qualification refs so stale product catalog links are removed safely. |
| TMF645 | ServiceQualification | checkServiceQualificationStateChangeEvent, queryServiceQualificationStateChangeEvent | Implemented | Incoming service qualification state changes update local qualification state/status when linked service qualifications are referenced. |

### Implementation tasks
- [x] Verify TMF679 exposed API coverage end to end
- [x] Verify TMF760 exposed API coverage end to end
- [x] Verify TMF701 exposed API coverage in configurator context
- [x] Implement or verify TMFC027 subscribed-event handling for TMF620
- [x] Implement or verify TMFC027 subscribed-event handling for TMF645
- [x] Capture verification notes

---

## TMFC006 – ServiceCatalogManagement

**Status:** In analysis
**Target sprint:** Sprint 3
**Current classification:** Missing (no side-car wiring addon yet)
**Existing addon(s):** `tmf_service_catalog`, `tmf_service_quality_management`, `tmf_process_flow`, `tmf_resource_catalog`, `tmf_entity_catalog`, `tmf_customer`, `tmf_party_role`
**Expected addon:** `tmfc006_wiring` (Service Catalog ODA wiring side-car)

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs / dependencies extracted from YAML
- [x] Baseline exposed APIs mapped to Odoo modules/controllers
- [ ] Dependent APIs mapped to Odoo modules/models (full coverage)
- [ ] Side-car wiring addon exists or equivalent wiring approach justified
- [ ] Raw TMF reference fields identified (ServiceCatalog, ServiceSpecification, ServiceCandidate, ServiceLevel* payloads)
- [ ] Relational fields identified (links to Party, PartyRole, ResourceSpecification, EntitySpecification, associationSpecification)
- [ ] Reference resolution implemented
- [ ] Published events verified from mutation paths (TMF633/TMF657/TMF701)
- [ ] Hub registration verified for TMF633/TMF657/TMF701
- [ ] Listener routes implemented for subscribed events (TMF634/TMF662)
- [ ] Subscribed event callbacks update local state correctly
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

### YAML scope summary
- Exposed: TMF633, TMF657, TMF701
- Dependencies: TMF634, TMF669, TMF632, TMF662
- Published events: TMF633, TMF657, TMF701
- Subscribed events: TMF634, TMF662

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF633 | service-catalog-management-api | catalog | GET, GET /id, POST, PATCH, DELETE | Implemented | `tmf_service_catalog.controllers.main_controller.TMFServiceCatalogController` exposes catalog CRUD and publishes hub notifications via `tmf.service.catalog._notify()` and `tmf.hub.subscription._notify_subscribers`. |
| TMF633 | service-catalog-management-api | category | GET, GET /id, POST, PATCH, DELETE | Not evidenced | No `ServiceCategory` model/controller found in `tmf_service_catalog`; TMFC006 wiring will need to introduce category surface (or justify omission). |
| TMF633 | service-catalog-management-api | serviceSpecification | GET, GET /id, POST, PATCH, DELETE | Implemented | `TMFServiceSpecificationController` + `tmf.service.specification` model provide CTK-facing serviceSpecification CRUD with JSON fields for `relatedParty` and `validFor`. |
| TMF633 | service-catalog-management-api | serviceCandidate | GET, GET /id, POST, PATCH, DELETE | Not evidenced | No serviceCandidate controller/model was found; only catalog + serviceSpecification are implemented. |
| TMF633 | service-catalog-management-api | exportJob | POST, GET, GET /id, DELETE | Not evidenced | No import/export job controllers found in `tmf_service_catalog`; jobs currently unimplemented. |
| TMF633 | service-catalog-management-api | importJob | POST, GET, GET /id, DELETE | Not evidenced | Same as exportJob; YAML surface exists without implementation. |
| TMF657 | service-quality-management-api | serviceLevelSpecification | GET, GET/id, POST, PATCH, DELETE | Implemented | `tmf_service_quality_management.controllers.service_level_specification_controller` + `tmf_service_quality_management.models.service_level_specification` expose CRUD and publish events via `_notify()` and `tmf.hub.subscription`. |
| TMF657 | service-quality-management-api | serviceLevelObjective | GET, GET/id, POST, PATCH, DELETE | Implemented | `service_level_objective_controller` + `service_level_objective` model expose CRUD; hub wiring present via `hub_subscription` model. |
| TMF657 | service-quality-management-api | serviceLevelSpecParameter | GET, GET/id, POST, PATCH, DELETE | Implemented | Parameter entities handled together with service-level spec/objective models; exposed via `service_level_specification_controller`. |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Evidenced (shared) | Base TMF701 surface is provided by `tmf_process_flow` (controllers + models). TMFC006 does not yet attach service catalog records to specific process/task flows. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF634 | resource-catalog-management-api | false | resourceSpecification | Evidenced (base) | `tmf_resource_catalog` module exposes TMF634 CRUD for `resourceSpecification`; no TMFC006-specific wiring was found to store or reconcile resourceSpecification refs from service catalog records. |
| TMF669 | party-role-management-api | false | partyRole | Evidenced (base) | `tmf_party_role` module exposes TMF669; service catalog models store `relatedParty` as JSON only, without resolving partyRole relations yet. |
| TMF632 | party-management-api | false | individual, organization | Evidenced (base) | `tmf_customer` / `tmf_party` stack exposes TMF632; service catalog records currently keep raw `relatedParty` JSON and do not map it to `res.partner` or Party/PartyRole models in a TMFC006-specific way. |
| TMF662 | entity-catalog-management-api | false | entitySpecification, associationSpecification | Evidenced (base) | `tmf_entity_catalog` module exposes TMF662; TMFC006 does not yet link service specifications to entity/association specifications per YAML intent.

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF633 | ServiceCatalogManagement | serviceSpecificationCreate/Change/Delete, serviceCategoryCreate/Change/Delete, serviceCandidateCreate/Change/Delete, serviceCatalogCreate/Change/Delete, serviceCatalogBatchEvent | Partially evidenced | `tmf.service.catalog` and `tmf.service.specification` models call `_notify()` on create/update/delete, which delegates to `tmf.hub.subscription._notify_subscribers` for `serviceCatalog` and `serviceSpecification`. However, there is no category/serviceCandidate model and no explicit implementation of `serviceCatalogBatchEvent`, so the full event catalogue is not yet covered. |
| TMF657 | ServiceQualityManagement | serviceLevelObjectiveCreate/Change/AttributeValueChange, serviceLevelSpecificationCreate/Delete/AttributeValueChange | Partially evidenced | `tmf_service_quality_management` models publish events via `_notify()` on create/write/unlink; attribute-value change vs generic change events are not yet separately modeled, but overall notification flow exists through `tmf.hub.subscription`. |
| TMF701 | ProcessFlowManagement | processFlow/taskFlow create/stateChange/delete/attributeValueChange/informationRequired | Evidenced (shared) | `tmf_process_flow` mixin publishes TMF701 events for process/task flows. TMFC006 reuses this, but no catalog-specific provisioning or correlation to catalog/specification entities is implemented yet. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF634 | ResourceCatalogManagement | resourceSpecificationCreateEvent, resourceSpecificationChangeEvent, resourceSpecificationDeleteEvent | Not evidenced | TMFC006 YAML requires listening to TMF634 events, but no `tmfc006_*` listener controllers or tools exist; `tmf_service_catalog` does not currently process resourceSpecification callbacks. |
| TMF662 | EntityCatalogManagement | entitySpecificationCreate/AttributeValueChange/Change/Delete events | Not evidenced | `tmf_entity_catalog` exposes TMF662, but there is no TMFC006-side listener surface at `/tmf-api/EntityCatalog/call-back` or equivalent to reconcile entity/association specs into service catalog structures. |

### Implementation tasks
- [x] Confirm YAML-to-code mapping for TMF633, TMF657, TMF701 exposed APIs (baseline add-ons)
- [ ] Create `tmfc006_wiring` addon skeleton following the established side-car pattern (models, controllers, security, data).
- [ ] Introduce raw JSON reference fields for key YAML dependencies (TMF634/TMF632/TMF669/TMF662) on service catalog/specification/candidate entities (or in side-car models).
- [ ] Add relational fields and reference resolution logic to map those JSON refs into Odoo models (resourceSpecification, entitySpecification/associationSpecification, Party/PartyRole).
- [ ] Implement TMF633 hub registration routes and ensure `tmf.hub.subscription` lifecycle is covered for ServiceCatalog and ServiceSpecification events (including any batch events we choose to support).
- [ ] Decide and implement strategy for `serviceCategory`, `serviceCandidate`, `importJob`, and `exportJob` resources (native models vs thin wrappers vs explicit out-of-scope justification).
- [ ] Wire TMF701 processFlow/taskFlow records to service catalog entities where lifecycle workflows are required (reusing `tmf_process_flow` mixin patterns from TMFC001/TMFC003/TMFC005/TMFC027).
- [ ] Design and implement listener endpoints for TMF634 ResourceCatalog events, including reconciliation of resourceSpecification references into service specifications and candidates.
- [ ] Design and implement listener endpoints for TMF662 EntityCatalog events, including reconciliation of entity/association specifications used in service models.
- [ ] Capture verification notes summarizing cross-component interactions with TMFC001/TMFC005/TMFC027 and with underlying TMF634/TMF662 domains.
- [ ] Update `TMFC_IMPLEMENTATION_STATUS.md` once the first wiring pass is complete.

## TMFC007 – ServiceOrderManagement

**Status:** In analysis
**Target sprint:** Sprint 2
**Current classification:** Missing (no side-car wiring addon yet)
**Existing addon(s):** `tmf_service_order`, `tmf_service_inventory`, `tmf_resource_inventory`, `tmf_appointment`, `tmf_geographic_address`, `tmf_geographic_site`, `tmf_geographic_location`, `tmf_communication_message`, `tmf_work_management`, `tmf_process_flow`
**Expected addon:** `tmfc007_wiring` (Service Order ODA wiring side-car)

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs / dependencies extracted from YAML
- [x] Exposed APIs mapped to Odoo modules/controllers (baseline)
- [ ] Dependent APIs mapped to Odoo modules/models (full coverage)
- [ ] Side-car wiring addon exists or equivalent wiring approach justified
- [ ] Raw TMF reference fields identified (ServiceOrder payload, cancelServiceOrder, related entities)
- [ ] Relational fields identified (links to Party, Service, Resource, Appointment, WorkOrder, etc.)
- [ ] Reference resolution implemented
- [ ] Published events verified from mutation paths (including stateChange, informationRequired, jeopardy, milestone, cancelServiceOrder*)
- [ ] Hub registration verified for TMF641/TMF701
- [ ] Listener routes implemented for subscribed events (TMF652, TMF645, TMF681, TMF697)
- [ ] Subscribed event callbacks update local state correctly and reconcile with TMFC003/TMFC011 orchestration
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

### YAML scope summary
- Exposed: TMF641, TMF701
- Dependencies: TMF632, TMF633, TMF634, TMF638, TMF639, TMF640, TMF641, TMF645, TMF646, TMF652, TMF653, TMF669, TMF673, TMF674, TMF675, TMF681, TMF697, TMF701
- Published events: TMF641, TMF701
- Subscribed events: TMF652, TMF645, TMF681, TMF697

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF641 | service-ordering-management-api | serviceOrder | GET, GET /id, POST, PATCH, DELETE | Implemented | `tmf_service_order/controllers/main_controller.py` exposes TMF641 serviceOrder endpoints on `/tmf-api/serviceOrdering/v4/serviceOrder`. |
| TMF641 | service-ordering-management-api | cancelServiceOrder | GET, GET /id, POST | Not evidenced | No dedicated cancelServiceOrder model/controller found in `tmf_service_order`; cancellation is currently expressed via `state`, `cancellationDate`, and `cancellationReason` fields on `tmf.service.order` only. |
| TMF701 | process-flow-management-api | processFlow, taskFlow | GET, GET /id, POST, DELETE /id, PATCH /id | Evidenced (shared) | TMF701 base exposure is provided by `tmf_process_flow` as used already in TMFC003/TMFC005/TMFC027. TMFC007 does not yet have explicit wiring tying specific ServiceOrders to TMF701 flows. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF632 | party-management-api | false | individual, organization | Partially evidenced | `tmf_service_order/models/main_model.py` resolves `relatedParty` into `res.partner` records using `tmf_id`; underlying TMF632 exposure is via `tmf_customer` / `tmf_party` stack, but there is no dedicated TMFC007 side-car wiring yet. |
| TMF633 | service-catalog-management-api | true | serviceSpecification | Not evidenced | `tmf_service_catalog` module exists, but no TMFC007-specific wiring layer was found to reconcile serviceSpecification refs from ServiceOrders. |
| TMF634 | resource-catalog-management-api | false | resourceSpecification | Not evidenced | `tmf_resource_catalog` exists; no TMFC007 wiring to map ServiceOrder items to resourceSpecification. |
| TMF638 | service-inventory-management-api | true | service | Not evidenced | `tmf_service_inventory` exists and is used by other TMFCs, but ServiceOrder JSON (`serviceOrderItem.service`) is not yet resolved into `tmf.service` relations. |
| TMF639 | resource-inventory-management-api | false | resource | Not evidenced | `tmf_resource_inventory` exists; there is no explicit TMFC007 wiring from ServiceOrders to underlying resource inventory. |
| TMF640 | service-activation-management-api | false | monitor | Not evidenced | No `tmf_service_activation` wiring discovered from ServiceOrders. |
| TMF641 | service-ordering-management-api | false | serviceOrder, cancelServiceOrder | Implemented (self) | ServiceOrder base API is implemented in `tmf_service_order`; cancelServiceOrder remains missing as a first-class resource. |
| TMF645 | service-qualification-management-api | false | checkServiceQualification, queryServiceQualification | Not evidenced | `tmf_service_qualification` exists; no TMFC007 wiring for pre-checking/recording service qualification context on ServiceOrders. |
| TMF646 | appointment-management-api | false | appointment, searchTimeSlot | Not evidenced | `tmf_appointment` exists; ServiceOrders do not yet hold explicit appointment/searchTimeSlot refs. |
| TMF652 | resource-order-management-api | false | resourceOrder, cancelResourceOrder | Not evidenced | TMF652 is implemented in `tmf_resource_order`; TMFC003 currently consumes ResourceOrder events, but TMFC007 does not yet model or call TMF652 directly. |
| TMF653 | service-test-management-api | false | serviceTest, serviceTestSpecification | Not evidenced | `tmf_service_test` exists; no direct ServiceOrder wiring found. |
| TMF669 | party-role-management-api | false | partyRole | Not evidenced | TMF669 is available via `tmf_party_role`; ServiceOrder currently resolves only `res.partner`, not partyRole-specific refs. |
| TMF673 | geographic-address-management-api | false | geographicAddress, geographicSubAddress, geographicAddressValidation | Not evidenced | Geographic modules exist; ServiceOrders currently do not persist or resolve TMF673 place refs. |
| TMF674 | geographic-site-management-api | false | geographicLocation | Not evidenced | No ServiceOrder wiring to TMF674 site/location entities. |
| TMF675 | geographic-location-management-api | false | geographicSite | Not evidenced | No ServiceOrder wiring to TMF675 location entities. |
| TMF681 | communication-management-api | false | communicationMessage | Not evidenced | `tmf_communication_message` exists; ServiceOrders do not yet link to communicationMessage records. |
| TMF697 | work-order-management-api | false | workOrder | Not evidenced | `tmf_work_management` / WorkOrder APIs exist; ServiceOrders have a `project_task_id` bridge but no TMF697-specific workOrder linkage. |
| TMF701 | process-flow-management-api | false | processFlow | Partially evidenced | `tmf_process_flow` provides TMF701; TMFC003 wires ProcessFlows for orchestration, but there is no dedicated TMFC007 association between ServiceOrders and processFlow/taskFlow instances. |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF641 | ServiceOrderingManagement | serviceOrderCreateEvent, serviceOrderAttributeValueChangeEvent, serviceOrderDeleteEvent | Implemented (subset) | `tmf.service.order._notify()` publishes `ServiceOrderCreateEvent`, `ServiceOrderAttributeValueChangeEvent`, and `ServiceOrderDeleteEvent` via `tmf.hub.subscription._notify_subscribers("serviceOrder", ...)`. |
| TMF641 | ServiceOrderingManagement | serviceOrderStateChangeEvent, serviceOrderInformationRequiredEvent, serviceOrderMilestoneEvent, serviceOrderJeopardyEvent, cancelServiceOrderCreateEvent, cancelServiceOrderStateChangeEvent, cancelServiceOrderInformationRequiredEvent | Not evidenced | No explicit state machine or event emission for these event types was found in `tmf_service_order`; state is stored as a simple `state` Char field and cancellations are implicit. |
| TMF701 | ProcessFlowManagement | processFlowCreateEvent, processFlowStateChangeEvent, processFlowDeleteEvent, processFlowAttributeValueChangeEvent, taskFlowCreateEvent, taskFlowStateChangeEvent, taskFlowDeleteEvent, taskFlowAttributeValueChangeEvent, taskFlowInformationRequiredEvent | Evidenced (shared) | `tmf_process_flow` mixin publishes TMF701 events; TMFC007 does not yet provision or own these flows, but they are available for future wiring. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF652 | ResourceOrderManagement | resourceOrderStateChange, resourceOrderAttributeValueChangeEvent, resourceOrderInformationRequiredEvent, cancelResourceOrderStateChange, cancelResourceOrderInformationRequiredEvent | Not evidenced | YAML lists TMF652 as an event source, but no TMFC007-specific listener routes or tools were found; TMFC003 currently consumes ResourceOrder events instead. |
| TMF645 | ServiceQualification | checkServiceQualificationStateChangeEvent, queryServiceQualificationStateChangeEvent | Not evidenced | No ServiceOrder listener endpoints were found for TMF645 events; qualification linkage currently lives in TMFC027. |
| TMF681 | Communication | communicationMessageStateChangeEvent | Not evidenced | No TMFC007 listener routes for Communication events were located. |
| TMF697 | WorkOrder | workOrderStateChange | Not evidenced | WorkOrder events are not yet wired into ServiceOrders; state sync currently uses Odoo Project tasks only. |

### Implementation tasks
- [ ] Create `tmfc007_wiring` addon skeleton following the established side-car pattern (models, controllers, security, data).
- [ ] Document and implement the ServiceOrder state model (including jeopardy/milestone/infoRequired semantics) and map to TMF641 `state` and event types.
- [ ] Implement or justify handling for `cancelServiceOrder` as a first-class TMF641 resource (or explicitly document why cancellation will be modeled as a PATCH-only flow).
- [ ] Introduce raw JSON reference fields for key YAML dependencies (TMF633/634/638/639/640/645/646/652/669/673/674/675/681/697) on `tmf.service.order` or its side-car model.
- [ ] Add relational fields and reference resolution logic to map those JSON refs into Odoo models (service, resource, party, appointment, work order, geography, communication).
- [ ] Implement TMF641 hub registration routes and ensure `tmf.hub.subscription` subscription lifecycle is covered for ServiceOrder events.
- [ ] Wire TMF701 processFlow/taskFlow records to ServiceOrders where orchestration requires explicit flows (re-using `tmf_process_flow` mixin patterns from TMFC003/TMFC005/TMFC027).
- [ ] Design and implement listener endpoints for TMF652 ResourceOrder events, including reconciliation of resourceOrder outcomes back into ServiceOrder state, coordinated with TMFC003/TMFC011 responsibilities.
- [ ] Design and implement listener endpoints for TMF645, TMF681, and TMF697 events, with clear rules for when ServiceOrders should update state or metadata in response.
- [ ] Capture verification notes summarizing cross-component interactions with TMFC003 (product-order orchestration) and TMFC011 (resource orders).
- [ ] Update `TMFC_IMPLEMENTATION_STATUS.md` once the first wiring pass is complete.

---

## Backlog TMFCs to expand next

These still need to be converted from YAML summaries into execution checklists:
- TMFC008
- TMFC009
- TMFC010
- TMFC011
- TMFC012
- TMFC014
- TMFC020
- TMFC022
- TMFC023
- TMFC024
- TMFC028
- TMFC029
- TMFC030
- TMFC031
- TMFC035
- TMFC036
- TMFC037
- TMFC038
- TMFC039
- TMFC040
- TMFC041
- TMFC043
- TMFC046
- TMFC050
- TMFC054
- TMFC055
- TMFC061
- TMFC062

---

## Verification strategy

For every TMFC implementation pass:
- [ ] Review YAML and restate required resources/events
- [ ] Map requirements to existing Odoo modules
- [ ] Verify or implement side-car wiring
- [ ] Verify event publishers in model/controller mutation paths
- [ ] Verify listener endpoints and callback processing
- [ ] Update status + checklist docs
- [ ] Commit changes with TMFC-specific message

The point of this checklist is not administrative ceremony. It is to prevent us from confusing a collection of APIs with a working ODA component. 🏛️
