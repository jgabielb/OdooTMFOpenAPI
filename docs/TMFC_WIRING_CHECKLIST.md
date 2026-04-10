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

[... existing sections above TMFC006 unchanged ...]

## TMFC006 – ServiceCatalogManagement

**Status:** Partially wired
**Target sprint:** Sprint 3
**Current classification:** Partially wired (first wiring pass)
**Existing addon(s):** `tmf_service_catalog`, `tmf_service_quality_management`, `tmf_process_flow`, `tmf_resource_catalog`, `tmf_entity_catalog`, `tmf_customer`, `tmf_party_role`
**New addon:** `tmfc006_wiring` (Service Catalog ODA wiring side-car)

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs / dependencies extracted from YAML
- [x] Baseline exposed APIs mapped to Odoo modules/controllers
- [x] Side-car wiring addon exists or equivalent wiring approach justified (`tmfc006_wiring`)
- [x] Raw TMF reference fields identified for foundational dependencies (TMF634/TMF632/TMF669/TMF662)
- [x] Relational fields identified for foundational dependencies (Party/PartyRole/ResourceSpecification/EntitySpecification)
- [ ] Dependent APIs mapped to Odoo modules/models (full coverage)
- [ ] Reference resolution implemented (beyond scaffolding helpers)
- [ ] Published events verified from mutation paths (TMF633/TMF657/TMF701)
- [x] Hub registration verified for TMFC006-specific façade (`/tmfc006/hub/*`)
- [x] Listener routes implemented for subscribed events (TMF634/TMF662)
- [ ] Subscribed event callbacks update local state correctly (reconciliation still a no-op)
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after broader wiring pass

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
| TMF657 | service-quality-management-api | serviceLevelSpecification | GET, GET/id, POST, PATCH, DELETE | Implemented | `tmf_service_quality_management.controllers.service_level_specification_controller` + `tmf_service_quality_management.models.service_level_specification` expose CRUD and publish events via `_notify()` and `tmf.hub.subscription`. TMFC006 pass 1 does not alter this surface. |
| TMF657 | service-quality-management-api | serviceLevelObjective | GET, GET/id, POST, PATCH, DELETE | Implemented | `service_level_objective_controller` + `service_level_objective` model expose CRUD; hub wiring present via `hub_subscription` model. TMFC006 pass 1 leaves this unchanged. |
| TMF657 | service-quality-management-api | serviceLevelSpecParameter | GET, GET/id, POST, PATCH, DELETE | Implemented | Parameter entities handled together with service-level spec/objective models; exposed via `service_level_specification_controller`. |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Evidenced (shared) | Base TMF701 surface is provided by `tmf_process_flow` (controllers + models). TMFC006 pass 1 only introduces a hub façade (`/tmfc006/hub/serviceCatalog` and `/tmfc006/hub/serviceQuality`) and does not yet attach service catalog records to specific process/task flows. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF634 | resource-catalog-management-api | false | resourceSpecification | Evidenced (base) | `tmf_resource_catalog` module exposes TMF634 CRUD for `resourceSpecification`. TMFC006 pass 1 adds JSON + relational fields on `tmfc006.wiring.tools` to carry resourceSpecification references, but does not yet implement reconciliation logic. |
| TMF669 | party-role-management-api | false | partyRole | Evidenced (base) | `tmf_party_role` module exposes TMF669. TMFC006 pass 1 introduces `party_role_ids` on `tmfc006.wiring.tools` for future mapping from serviceSpecification-relatedParty payloads. |
| TMF632 | party-management-api | false | individual, organization | Evidenced (base) | `tmf_customer` / `tmf_party` stack exposes TMF632. TMFC006 pass 1 adds `related_partner_ids` on `tmfc006.wiring.tools`, but keeps existing `relatedParty` JSON on `tmf.service.catalog` / `tmf.service.specification` unchanged. |
| TMF662 | entity-catalog-management-api | false | entitySpecification, associationSpecification | Evidenced (base) | `tmf_entity_catalog` module exposes TMF662. TMFC006 pass 1 adds `entity_specification_ids` and JSON scaffolding fields on `tmfc006.wiring.tools` for future association, but does not yet perform reconciliation.

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF633 | ServiceCatalogManagement | serviceSpecificationCreate/Change/Delete, serviceCategoryCreate/Change/Delete, serviceCandidateCreate/Change/Delete, serviceCatalogCreate/Change/Delete, serviceCatalogBatchEvent | Partially evidenced | `tmf.service.catalog` and `tmf.service.specification` models call `_notify()` on create/update/delete, which delegates to `tmf.hub.subscription._notify_subscribers` for `serviceCatalog` and `serviceSpecification`. No TMFC006-specific publishers are introduced in pass 1. |
| TMF657 | ServiceQualityManagement | serviceLevelObjectiveCreate/Change/AttributeValueChange, serviceLevelSpecificationCreate/Delete/AttributeValueChange | Partially evidenced | `tmf_service_quality_management` models publish events via `_notify()` on create/write/unlink; attribute-value change vs generic change events are not yet separately modeled. TMFC006 pass 1 does not adjust this behaviour. |
| TMF701 | ProcessFlowManagement | processFlow/taskFlow create/stateChange/delete/attributeValueChange/informationRequired | Evidenced (shared) | `tmf_process_flow` mixin publishes TMF701 events for process/task flows. TMFC006 pass 1 does not yet provision or correlate flows to ServiceCatalog entities.

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF634 | ResourceCatalogManagement | resourceSpecificationCreateEvent, resourceSpecificationChangeEvent, resourceSpecificationDeleteEvent | Partially wired (scaffolding) | `/tmfc006/listener/resourceSpecification` JSON endpoint implemented in `tmfc006_wiring.controllers.listeners`. Pass 1 delegates to `tmfc006.wiring.tools._handle_resource_catalog_event(payload)`, which currently returns `True` without mutating state. URLs and basic listener surface are now stable for future reconciliation work. |
| TMF662 | EntityCatalogManagement | entitySpecificationCreate/AttributeValueChange/Change/Delete events | Partially wired (scaffolding) | `/tmfc006/listener/entitySpecification` JSON endpoint implemented in `tmfc006_wiring.controllers.listeners` and delegated to `tmfc006.wiring.tools._handle_entity_catalog_event(payload)`. This provides a safe, no-op listener surface for TMF662 while we design reconciliation rules. |

### Implementation tasks (pass 1)
- [x] Confirm YAML-to-code mapping for TMF633, TMF657, TMF701 exposed APIs (baseline add-ons).
- [x] Create `tmfc006_wiring` addon skeleton following the established side-car pattern (models, controllers, security, data).
- [x] Introduce raw JSON reference fields for key YAML dependencies (TMF634/TMF632/TMF669/TMF662) on a shared `tmfc006.wiring.tools` abstract model, without altering TMF633 baseline models.
- [x] Add relational fields for foundational dependencies (`related_partner_ids`, `party_role_ids`, `resource_specification_ids`, `entity_specification_ids`) aligned with existing TMF modules.
- [x] Implement TMFC006-specific hub façade routes backed by `tmf.hub.subscription` (`/tmfc006/hub/serviceCatalog`, `/tmfc006/hub/serviceQuality`).
- [x] Design and implement listener endpoints for TMF634 ResourceCatalog events (scaffolding only) and TMF662 EntityCatalog events (scaffolding only).
- [ ] Extend `_resolve_service_spec_references` to perform concrete mapping from TMF633 payloads into TMF632/TMF669/TMF634/TMF662 relations once sample payloads are available.
- [ ] Wire TMF701 processFlow/taskFlow records to service catalog entities where lifecycle workflows are required (reusing `tmf_process_flow` mixin patterns from TMFC001/TMFC003/TMFC005/TMFC027).
- [ ] Capture verification notes summarizing cross-component interactions with TMFC001/TMFC005/TMFC027 and with underlying TMF634/TMF662 domains.
- [ ] Update `TMFC_IMPLEMENTATION_STATUS.md` once the broader TMFC006 wiring pass is complete.

---

## TMFC008 – ServiceInventory

**Status:** In analysis
**Target sprint:** Sprint 3
**Current classification:** Missing (no `tmfc008_*` wiring addon; base TMF638 module exists)
**Existing addon(s):** `tmf_service_inventory`, `tmf_process_flow`, `tmf_resource_inventory`, `tmf_resource_catalog`, `tmf_geographic_address`, `tmf_geographic_site`, `tmf_geographic_location`, `tmf_customer`, `tmf_party_role`, `tmf_service_order`
**New addon:** `tmfc008_wiring` (Service Inventory ODA wiring side-car)

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs / dependencies extracted from YAML
- [x] Baseline exposed APIs mapped to Odoo modules/controllers (TMF638/TMF701)
- [ ] Dependent APIs mapped to Odoo modules/models (full coverage)
- [ ] Side-car wiring addon exists or equivalent wiring approach justified (`tmfc008_wiring`)
- [ ] Raw TMF reference fields identified (ServiceInventory ↔ ServiceCatalog/ResourceInventory/Party/Geo/ServiceOrder)
- [ ] Relational fields identified (links to serviceSpecification, resource, party/partyRole, geographicSite/location, serviceOrder)
- [ ] Reference resolution implemented
- [ ] Published events verified from mutation paths (TMF638/TMF701)
- [ ] Hub registration verified for TMFC008-specific façade (if added on top of base `tmf_service_inventory`)
- [ ] Listener routes implemented for subscribed events (TMF639/TMF638/TMF633/TMF669/TMF674/TMF675/TMF632/TMF641)
- [ ] Subscribed event callbacks update local state correctly
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after broader wiring pass

### YAML scope summary
- Exposed: TMF638, TMF701
- Dependencies: TMF633, TMF669, TMF639, TMF638, TMF673, TMF674, TMF675, TMF641, TMF632, TMF672
- Published events: TMF638, TMF701
- Subscribed events: TMF639, TMF638, TMF633, TMF669, TMF674, TMF675, TMF632, TMF641

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF638 | service-inventory-management-api | service | GET, GET /id, POST, PATCH, DELETE | Implemented | `tmf_service_inventory.controllers.service_controller.TMFServiceController` exposes CTK-facing TMF638 routes for listing, retrieving, creating, patching, and deleting Service records (`tmf.service`). |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Evidenced (shared) | Base TMF701 ProcessFlow/TaskFlow surface is provided by `tmf_process_flow`. TMFC008 does not yet provision or link flows to Service Inventory records; this will be introduced in `tmfc008_wiring`. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF633 | service-catalog-management-api | true | serviceSpecification | Partially evidenced | `tmf.service` currently links to `tmf.product.specification` via `product_specification_id` and exposes this as `serviceSpecification` in `to_tmf_json()`. True ServiceSpecification (`tmf.service.specification`) is provided by `tmf_service_catalog`, but TMFC008-specific reconciliation between ServiceInventory and ServiceCatalog is not yet implemented. |
| TMF669 | party-role-management-api | false | partyRole | Not evidenced | `tmf.service` relates to `res.partner` (`partner_id`) and, for v4 responses, exposes relatedParty/PartyRef in `to_tmf_json()`. No explicit TMF669 PartyRole wiring or side-car relations are present yet. |
| TMF639 | resource-inventory-management-api | false | resource | Evidenced (base) | `tmf.service` links to `stock.lot` as `resource_id`, and `to_tmf_json()` exposes this as `supportingResource` with TMF639-style `ResourceRef`. TMF639 CRUD and events are provided by `tmf_resource_inventory`. TMFC008-specific reconciliation for resource delete/change events is not yet present. |
| TMF638 | service-inventory-management-api | false | service | Evidenced | Self-dependency (read paths) is covered by the TMF638 controllers in `tmf_service_inventory`. |
| TMF673 | geographic-address-management-api | false | geographicAddress, geographicSubAddress | Not evidenced | No `place`/geographic address fields or relations are present on `tmf.service` in the current codebase. |
| TMF674 | geographic-site-management-api | false | geographicSite | Not evidenced | No explicit geographicSite linkage exists on `tmf.service`; geo wiring is currently done on Product/Resource inventory components instead. |
| TMF675 | geographic-location-management-api | false | geographicLocation | Not evidenced | No `geographicLocation` references or relations are present on `tmf.service`. |
| TMF641 | service-ordering-management-api | false | serviceOrder | Partially evidenced | `tmf_service_inventory.models.sale_order.SaleOrder.action_confirm` creates `tmf.service` records from `sale.order` lines, giving TMFC003/TMFC007 a path to link ServiceOrder → Service. TMFC008 does not yet have explicit `serviceOrder` reference fields or listeners for ServiceOrder delete events. |
| TMF632 | party-management-api | false | individual, organization | Evidenced (base) | Party/Customer APIs are provided by the `tmf_customer` / `tmf_party` stack. `tmf.service.partner_id` references `res.partner`, and `to_tmf_json()` optionally emits TMF632-style PartyRef when v4 routes are used, but there is no TMFC008-specific delete-event reconciliation yet. |
| TMF672 | permission-management-api | false | permission | Not evidenced | TMFC008 YAML lists Permission as a dependency for read access control. No explicit TMF672 wiring has been identified in `tmf_service_inventory`; permission checks are currently handled by core Odoo ACLs rather than TMF672 resources. |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF638 | ServiceInventoryManagement | serviceCreateEvent, serviceAttributeValueChangeEvent, serviceStateChangeEvent, serviceDeleteEvent | Partially evidenced | `tmf.service.create/write/unlink` call `tmf.hub.subscription._notify_subscribers` with `api_name='service'` and `event_type` set to `create`, `update`, or `delete`. This provides notification coverage for create/update/delete, but does not yet distinguish state-change vs attribute-change events or publish explicit TMF638 event names. |
| TMF701 | ProcessFlowManagement | processFlowCreateEvent, processFlowStateChangeEvent, processFlowDeleteEvent, processFlowAttributeValueChangeEvent, taskFlowCreateEvent, taskFlowStateChangeEvent, taskFlowDeleteEvent, taskFlowAttributeValueChangeEvent, taskFlowInformationRequiredEvent | Evidenced (shared) | `tmf_process_flow` publishes TMF701 events for all flows. TMFC008 will need to provision and link suitable flows for service lifecycle management once `tmfc008_wiring` is introduced. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF639 | ResourceInventoryManagement | resourceDeleteEvent | Not evidenced (TMFC008) | No ServiceInventory-specific listener endpoints exist for ResourceInventory events. `tmfc005_wiring` currently handles resourceDeleteEvent for ProductInventory; TMFC008 will need its own callbacks to remove or update `supportingResource` links on `tmf.service`. |
| TMF638 | ServiceInventoryManagement | serviceCreateEvent, serviceAttributeValueChangeEvent, serviceStateChangeEvent, serviceDeleteEvent | Not evidenced (self-listener) | TMFC008 YAML models self-subscriptions for Service events (for cross-component sync). No corresponding listener routes or callback handlers exist yet in Odoo; existing code only publishes events. |
| TMF633 | ServiceCatalogManagement | serviceSpecificationDeleteEvent | Not evidenced | No ServiceInventory listener for ServiceCatalog events is present. Catalog delete events are currently handled in ProductInventory and Configurator wiring; TMFC008 should eventually reconcile `serviceSpecification` links when a serviceSpecification is removed. |
| TMF669 | PartyRoleManagement | partyRoleDeleteEvent | Not evidenced | No TMFC008-specific listener exists for PartyRole delete events; related party/role cleanup is handled in other TMFCs (e.g., TMFC001/TMFC005/TMFC027) but not for ServiceInventory records. |
| TMF674 | GeographicSiteManagement | geographicSiteDeleteEvent | Not evidenced | No ServiceInventory listener or geo linkage exists; any future `place` references on `tmf.service` will need delete-event reconciliation. |
| TMF675 | GeographicLocation | geographicLocationDeleteEvent | Not evidenced | As above; no current geographicLocation wiring on ServiceInventory. |
| TMF632 | PartyManagement | individualDeleteEvent, organizationDeleteEvent | Not evidenced | There is no TMFC008 listener for Party delete events; if a `res.partner` is deleted, `tmf.service` linkage is not explicitly reconciled by a ServiceInventory component. |
| TMF641 | ServiceOrderingManagement | serviceOrderDeleteEvent | Not evidenced | No ServiceInventory listener exists for ServiceOrder delete events. Downstream orchestration components (TMFC003/TMFC007) handle most ServiceOrder state changes, but TMFC008 does not yet respond to deletes. |

### Implementation tasks (pass 1)
- [x] Confirm YAML-to-code mapping for TMF638/TMF701 exposed APIs (baseline `tmf_service_inventory` + shared `tmf_process_flow`).
- [x] Capture current dependent API evidence from existing modules (`tmf_service_inventory`, `tmf_resource_inventory`, `tmf_service_catalog`, `tmf_customer`, `tmf_party_role`, `tmf_geographic_*`, `tmf_service_order`).
- [ ] Create `tmfc008_wiring` addon skeleton following the established side-car pattern (models, controllers, security, data).
- [ ] Introduce raw TMF reference fields on `tmf.service` or a shared `tmfc008.wiring.tools` model for ServiceCatalog, ResourceInventory, Party/PartyRole, GeographicSite/Location, and ServiceOrder references.
- [ ] Add relational fields to represent resolved dependencies (serviceSpecification/serviceSpecificationRef, supportingResource/resourceRefs, Party/PartyRole, geographicSite/geographicLocation, serviceOrder) without altering CTK payload shapes.
- [ ] Implement TMFC008-specific hub façade routes if needed (for example, `/tmfc008/hub/serviceInventory`) backed by `tmf.hub.subscription`.
- [ ] Design and implement listener endpoints for TMF639, TMF633, TMF669, TMF674, TMF675, TMF632, TMF641 (and any self-subscriptions) with idempotent reconciliation logic.
- [ ] Refine TMF638 event publication so that state-change vs attribute-change events are distinguishable where required by the YAML.
- [ ] Capture verification notes summarizing the ServiceInventory role in the product/service/resource chain (interactions with TMFC003, TMFC005, TMFC006, TMFC007).
- [ ] Update `TMFC_IMPLEMENTATION_STATUS.md` once the initial TMFC008 wiring pass is complete.

---

## TMFC007 – ServiceOrderExecutionAndManagement

**Status:** Partially wired (second wiring pass)
**Target sprint:** Sprint 4
**Current classification:** Partially wired (state-change + dependent wiring)
**Existing addon(s):** `tmf_service_order`, `tmf_service_inventory`, `tmf_resource_order`, `tmf_communication_message`, `tmf_work_management`, `tmfc003_wiring`
**New addon:** `tmfc007_wiring` (Service Order ODA wiring side-car)

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs / dependencies extracted from YAML
- [x] Baseline exposed APIs mapped to Odoo modules/controllers (TMF641/TMF701)
- [x] Side-car wiring addon exists or equivalent wiring approach justified (`tmfc007_wiring`)
- [x] Raw TMF reference fields identified for foundational dependencies (TMF638/TMF681/TMF697)
- [x] Relational fields identified for foundational dependencies (ServiceInventory/CommunicationMessage/Work↔ServiceOrder)
- [x] Reference resolution implemented for TMF638 (ServiceInventory) and for TMF681/TMF697 when events carry ServiceOrder refs
- [x] Published events verified from mutation paths (TMF641 create/update/delete + state-change/cancel)
- [x] Hub registration verified for TMFC007-specific façade (`/tmfc007/hub`)
- [x] Listener routes implemented for subscribed events (TMF652/TMF645/TMF681/TMF697)
- [x] Subscribed event callbacks update local state correctly where safe (TMF652 via TMFC003 delegation; TMF645/TMF681/TMF697 state reconcile + dependency wiring)
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after broader TMFC007 wiring pass

### YAML scope summary
- Exposed: TMF641, TMF701
- Dependencies: TMF638, TMF652, TMF645, TMF681, TMF697, TMF632, TMF669
- Published events: TMF641, TMF701
- Subscribed events: TMF652, TMF645, TMF681, TMF697

### Exposed TMF APIs / Resources

| TMF ID | API Name | Resource(s) | YAML operations | Evidence status | Notes |
|--------|----------|-------------|-----------------|-----------------|-------|
| TMF641 | service-ordering-management-api | serviceOrder | GET, GET /id, POST, PATCH, DELETE | Implemented | `tmf_service_order.controllers.main_controller.TMFServiceOrderController` exposes CTK-facing TMF641 routes backed by `tmf.service.order`. Base model publishes create/update/delete events via `_notify()` and syncs `project.task` links via `_sync_project_task()`. |
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Evidenced (shared) | `tmf_process_flow` provides the shared TMF701 API surface. TMFC007 reuses process/task flows linked from `tmfc003_wiring` and optional `process_flow_ids`/`task_flow_ids` on `tmf.service.order` without provisioning new flows in this pass. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF638 | service-inventory-management-api | false | service | Evidenced (wiring) | `TMFC007ServiceOrderWiring` adds `service_ref_json` (raw TMF638 ServiceRefOrValue from `serviceOrderItem.service`) and `service_ids` (Many2many to `tmf.service`). `_tmfc007_resolve_tmf_refs()` keeps JSON + relational links in sync on create/write without changing TMF641 payloads. |
| TMF652 | resource-order-management-api | false | resourceOrder | Evidenced (delegated) | TMF652 CRUD is provided by `tmf_resource_order`. TMFC007 listener `/tmfc007/listener/resourceOrder` accepts ResourceOrder events and forwards them to `tmfc003.wiring.tools.handle_resource_order_event()`, reusing the orchestration and state aggregation implemented by TMFC003. No additional state is held in TMFC007. |
| TMF645 | service-qualification-management-api | false | serviceQualification | Evidenced (wiring) | `tmf_service_qualification` provides TMF645 CRUD. TMFC007 listener `/tmfc007/listener/serviceQualification` invokes `TMFC007WiringTools.handle_service_qualification_event()`, which reconciles the local `tmf.service.qualification.state` field from incoming Check/QueryServiceQualification events when a matching `tmf_id` exists. |
| TMF681 | communication-management-api | false | communicationMessage | Evidenced (wiring) | `tmf_communication_message` implements TMF681. `TMFC007CommunicationWiring` extends `tmf.communication.message` with `tmfc007_service_order_ref_json` (raw ServiceOrder refs) and `tmfc007_service_order_ids` (Many2many to `tmf.service.order`). `handle_communication_event()` updates `state` and wires ServiceOrder links when TMF681 events carry `serviceOrder` references. |
| TMF697 | work-order-management-api | false | workOrder | Evidenced (wiring) | TMF713 Work/WorkSpecification are provided by `tmf_work_management`. TMFC007 treats `tmf.work` records as the local representation of TMF697 WorkOrders. `TMFC007WorkWiring` adds `tmfc007_service_order_ref_json` + `tmfc007_service_order_ids` and `handle_work_order_event()` updates `tmf.work.state` and ServiceOrder links when WorkOrder events contain `serviceOrder` refs. |
| TMF632 | party-management-api | false | individual, organization | Evidenced (base) | Party/Customer APIs are provided by the `tmf_customer` / `tmf_party` stack. `tmf.service.order` already resolves `partner_id` from `related_party` via `_resolve_partner_from_related_party()` and `_sync_project_task()`. TMFC007 does not yet add extra Party reconciliation beyond this base behaviour. |
| TMF669 | party-role-management-api | false | partyRole | Not yet wired | TMF669 base API is available through `tmf_party_role`. TMFC007 YAML lists PartyRole as a dependency, but no ServiceOrder↔PartyRole-specific wiring has been implemented in this pass to avoid guessing detailed role semantics. |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF641 | ServiceOrderingManagement | serviceOrderCreateEvent, serviceOrderAttributeValueChangeEvent, serviceOrderDeleteEvent | Evidenced (base) | `tmf.service.order` calls `_notify("create"/"update"/"delete")`, which publishes TMF641 events via `tmf.hub.subscription._notify_subscribers(api_name="serviceOrder", event_type=...)`. |
| TMF641 | ServiceOrderingManagement | serviceOrderStateChangeEvent, cancelServiceOrderStateChangeEvent | Evidenced (TMFC007) | `TMFC007ServiceOrderWiring` extends `tmf.service.order.write()` to detect `state` transitions and first-time `cancellation_date` assignments. `_tmfc007_notify_state_transitions()` publishes `ServiceOrderStateChangeEvent` and `CancelServiceOrderStateChangeEvent` with the latest `to_tmf_json()` payloads, without altering existing create/update/delete notifications. |
| TMF701 | ProcessFlowManagement | processFlow/taskFlow create/stateChange/delete/attributeValueChange/informationRequired | Evidenced (shared) | `tmf_process_flow` mixin publishes TMF701 events for all flows. TMFC007 reuses these events for any flows linked to service orders via `process_flow_ids`/`task_flow_ids` and/or TMFC003 wiring, but does not add new publishers. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF652 | ResourceOrderManagement | ResourceOrderStateChangeEvent, ResourceOrderAttributeValueChangeEvent, ResourceOrderInformationRequiredEvent, CancelResourceOrderStateChangeEvent, CancelResourceOrderInformationRequiredEvent | Partially wired (delegated) | `/tmfc007/listener/resourceOrder` validates `eventType` against `TMFC007_RESOURCE_ORDER_EVENTS` and forwards accepted events to `tmfc003.wiring.tools.handle_resource_order_event()`. TMFC003 owns the orchestration logic and state propagation for ResourceOrder↔ServiceOrder↔ProductOrder. |
| TMF645 | ServiceQualificationManagement | CheckServiceQualificationStateChangeEvent, QueryServiceQualificationStateChangeEvent | Wired | `/tmfc007/listener/serviceQualification` routes events to `handle_service_qualification_event()`, which updates local `tmf.service.qualification.state` when a matching `tmf_id` exists, using `skip_tmf_wiring` to avoid recursive notifications. |
| TMF681 | CommunicationManagement | CommunicationMessageStateChangeEvent | Wired | `/tmfc007/listener/communicationMessage` accepts TMF681 events and `handle_communication_event()` reconciles `tmf.communication.message.state` plus ServiceOrder dependency links (`tmfc007_service_order_ref_json`/`tmfc007_service_order_ids`) when `serviceOrder` references are present. |
| TMF697 | WorkOrderManagement | WorkOrderStateChangeEvent | Wired | `/tmfc007/listener/workOrder` accepts TMF697 events and `handle_work_order_event()` reconciles `tmf.work.state` and ServiceOrder links (`tmfc007_service_order_ref_json`/`tmfc007_service_order_ids`) based on `serviceOrder` references in the WorkOrder payload. |

### Implementation tasks (pass 2)
- [x] Confirm YAML-to-code mapping for TMF641/TMF701 exposed APIs and dependent TMF638/TMF652/TMF645/TMF681/TMF697 resources.
- [x] Extend `tmf.service.order` with TMFC007-specific TMF638 dependency wiring (`service_ref_json`/`service_ids`) and idempotent `_tmfc007_resolve_tmf_refs()` resolution.
- [x] Add TMFC007-safe TMF641 state-change publication on `tmf.service.order.write()` covering ServiceOrderStateChangeEvent and CancelServiceOrderStateChangeEvent without altering existing create/update/delete notifications.
- [x] Implement TMFC007 listener endpoints for TMF652/TMF645/TMF681/TMF697 (`/tmfc007/listener/*`) with envelope validation and 4xx/5xx handling.
- [x] Implement `TMFC007WiringTools.handle_service_qualification_event()` with state reconciliation for `tmf.service.qualification`.
- [x] Implement `TMFC007WiringTools.handle_communication_event()` and `TMFC007CommunicationWiring` to reconcile `tmf.communication.message.state` and wire CommunicationMessage↔ServiceOrder links from TMF681 events.
- [x] Implement `TMFC007WiringTools.handle_work_order_event()` and `TMFC007WorkWiring` to reconcile `tmf.work.state` and wire Work↔ServiceOrder links from TMF697 events.
- [x] Keep TMF652 orchestration delegated to TMFC003 (`tmfc003.wiring.tools`) to avoid duplicate or conflicting state propagation.
- [ ] Capture verification notes summarizing cross-component interactions between TMFC003/TMFC005/TMFC006/TMFC007 and underlying TMF638/TMF652/TMF681/TMF697 domains.
- [ ] Update `TMFC_IMPLEMENTATION_STATUS.md` once TMFC007 wiring matures beyond this pass.

---

[... remaining sections (backlog, verification strategy) unchanged ...]
