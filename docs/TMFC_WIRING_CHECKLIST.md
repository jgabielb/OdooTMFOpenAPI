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
- [x] Reference resolution implemented (foundational TMF632/TMF669/TMF634/TMF662 for ServiceSpecification)
- [ ] Published events verified from mutation paths (TMF633/TMF657/TMF701)
- [x] Hub registration verified for TMFC006-specific façade (`/tmfc006/hub/*`)
- [x] Listener routes implemented for subscribed events (TMF634/TMF662)
- [x] Subscribed event callbacks update local state for TMF634/TMF662 where safe (best-effort reconciliation)
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

### Implementation tasks (pass 1+2)
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

**Status:** Partially wired (second wiring pass)
**Target sprint:** Sprint 3
**Current classification:** Partially wired (dependency wiring + listeners)
**Existing addon(s):** `tmf_service_inventory`, `tmf_process_flow`, `tmf_resource_inventory`, `tmf_resource_catalog`, `tmf_geographic_address`, `tmf_geographic_site`, `tmf_geographic_location`, `tmf_customer`, `tmf_party_role`, `tmf_service_order`
**New addon:** `tmfc008_wiring` (Service Inventory ODA wiring side-car)

### Standard checklist
- [x] YAML reviewed
- [x] Exposed APIs / dependencies extracted from YAML
- [x] Baseline exposed APIs mapped to Odoo modules/controllers (TMF638/TMF701)
- [x] Dependent APIs mapped to Odoo modules/models (foundational coverage for TMF633/TMF639/TMF632/TMF669/TMF641; TMF673/TMF674/TMF675/TMF672 remain unimplemented)
- [x] Side-car wiring addon exists or equivalent wiring approach justified (`tmfc008_wiring`)
- [x] Raw TMF reference fields identified (ServiceInventory ↔ ServiceCatalog/ResourceInventory/Party/ServiceOrder)
- [x] Relational fields identified (links to serviceSpecification, resource, party/partyRole, serviceOrder; TMF701 process/task flows provisioned as optional Many2many)
- [x] Reference resolution implemented for TMF633/TMF639/TMF632/TMF669/TMF641 where local records already exist
- [ ] Published events verified from mutation paths (TMF638/TMF701)
- [x] Hub registration verified for TMFC008-specific façade (`/tmfc008/hub/serviceInventory`)
- [x] Listener routes implemented for subscribed events (TMF639/TMF638/TMF633/TMF669/TMF632/TMF641; geo and permission listeners deferred)
- [x] Subscribed event callbacks update local state correctly for TMF633/TMF639/TMF632/TMF669/TMF641 where safe (additive wiring only)
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
| TMF701 | process-flow-management-api | processFlow, taskFlow | POST, GET, GET /id, DELETE, PATCH | Partially wired (linkage only) | Base TMF701 ProcessFlow/TaskFlow surface is provided by `tmf_process_flow`. `tmfc008_wiring` adds optional Many2many links (`tmfc008_process_flow_ids` / `tmfc008_task_flow_ids`) on `tmf.service` so ServiceInventory records can be associated with existing flows without provisioning them. |

### Dependent TMF APIs / Resources

| TMF ID | API Name | Required? | Resource(s) | Evidence status | Notes |
|--------|----------|-----------|-------------|-----------------|-------|
| TMF633 | service-catalog-management-api | true | serviceSpecification | Partially wired (with dependency reconciliation) | `tmf.service` links to `tmf.product.specification` via `product_specification_id` and exposes this as `serviceSpecification` in `to_tmf_json()`. `tmf_service_catalog` provides true ServiceSpecification (`tmf.service.specification`), and `tmfc008_wiring` adds JSON + relational fields (`tmfc008_service_spec_ref_json`, `tmfc008_service_specification_ids`) plus listener-driven reconciliation so that ServiceSpecification events populate those fields for services already linked via `product_specification_id`. |
| TMF669 | party-role-management-api | false | partyRole | Partially wired (with conservative linkage) | `tmf.service` relates to `res.partner` (`partner_id`) and, for v4 responses, exposes relatedParty/PartyRef in `to_tmf_json()`. `tmfc008_wiring` introduces `tmfc008_related_party_json`, `tmfc008_related_partner_ids`, and `tmfc008_party_role_ids`, and listener callbacks keep these fields in sync with TMF632/TMF669 events without changing base partner/partyRole behaviour. |
| TMF639 | resource-inventory-management-api | false | resource | Partially wired (with dependency reconciliation) | `tmf.service` links to `stock.lot` as `resource_id`, and `to_tmf_json()` exposes this as `supportingResource` with TMF639-style `ResourceRef`. TMF639 CRUD and events are provided by `tmf_resource_inventory`. `tmfc008_wiring` adds additive JSON + relational fields (`tmfc008_supporting_resource_ref_json`, `tmfc008_supporting_resource_ids`) and the TMFC008 listener now keeps them in sync for Services that already point at a given Resource. |
| TMF638 | service-inventory-management-api | false | service | Evidenced | Self-dependency (read paths) is covered by the TMF638 controllers in `tmf_service_inventory`. |
| TMF673 | geographic-address-management-api | false | geographicAddress, geographicSubAddress | Not evidenced | No `place`/geographic address fields or relations are present on `tmf.service` in the current codebase. |
| TMF674 | geographic-site-management-api | false | geographicSite | Not evidenced | No explicit geographicSite linkage exists on `tmf.service`; geo wiring is currently done on Product/Resource inventory components instead. |
| TMF675 | geographic-location-management-api | false | geographicLocation | Not evidenced | No `geographicLocation` references or relations are present on `tmf.service`. |
| TMF641 | service-ordering-management-api | false | serviceOrder | Partially wired (with dependency reconciliation) | `tmf_service_inventory.models.sale_order.SaleOrder.action_confirm` creates `tmf.service` records from `sale.order` lines, giving TMFC003/TMFC007 a path to link ServiceOrder → Service. `tmfc008_wiring` introduces JSON + relational fields (`tmfc008_service_order_ref_json`, `tmfc008_service_order_ids`) and the TMFC008 listener now attaches ServiceOrders to Services based on `serviceOrderItem[*].service` references observed in TMF641 events. |
| TMF632 | party-management-api | false | individual, organization | Evidenced (base + dependency reconciliation) | Party/Customer APIs are provided by the `tmf_customer` / `tmf_party` stack. `tmf.service.partner_id` references `res.partner`, and `to_tmf_json()` optionally emits TMF632-style PartyRef when v4 routes are used. `tmfc008_wiring` enriches this with `tmfc008_related_party_json` and `tmfc008_related_partner_ids`, updated from TMF632 listener callbacks. |
| TMF672 | permission-management-api | false | permission | Not evidenced (out of scope for pass 1) | TMFC008 YAML lists Permission as a dependency for read access control. No explicit TMF672 wiring has been identified in `tmf_service_inventory` or `tmfc008_wiring`; permission checks are currently handled by core Odoo ACLs rather than TMF672 resources. |

### Published Events

| TMF ID | Hub/API | Event/resource names | Evidence status | Notes |
|--------|---------|----------------------|-----------------|-------|
| TMF638 | ServiceInventoryManagement | serviceCreateEvent, serviceAttributeValueChangeEvent, serviceStateChangeEvent, serviceDeleteEvent | Partially evidenced | `tmf.service.create/write/unlink` call `tmf.hub.subscription._notify_subscribers` with `api_name='service'` and `event_type` set to `create`, `update`, or `delete`. This provides notification coverage for create/update/delete, but does not yet distinguish state-change vs attribute-change events or publish explicit TMF638 event names. `tmfc008_wiring` adds a TMFC008-specific hub façade (`/tmfc008/hub/serviceInventory`) that reuses `tmf.hub.subscription`. |
| TMF701 | ProcessFlowManagement | processFlowCreateEvent, processFlowStateChangeEvent, processFlowDeleteEvent, processFlowAttributeValueChangeEvent, taskFlowCreateEvent, taskFlowStateChangeEvent, taskFlowDeleteEvent, taskFlowAttributeValueChangeEvent, taskFlowInformationRequiredEvent | Evidenced (shared) | `tmf_process_flow` publishes TMF701 events for all flows. TMFC008 will need to provision and link suitable flows for service lifecycle management once `tmfc008_wiring` is introduced. |

### Subscribed Events

| TMF ID | Source component/API | Event/resource names | Evidence status | Notes |
|--------|----------------------|----------------------|-----------------|-------|
| TMF639 | ResourceInventoryManagement | resourceDeleteEvent | Wired (dependency linkage) | `/tmfc008/listener/resourceInventory` JSON endpoint delegates to `tmfc008.wiring.tools.handle_resource_event()`, which resolves the referenced `stock.lot` by `tmf_id`/ID and, when found, ensures any `tmf.service` records that already point at it via `resource_id` also record it in `tmfc008_supporting_resource_ref_json` and `tmfc008_supporting_resource_ids`. No new resources are created and the primary `resource_id` linkage remains unchanged. |
| TMF638 | ServiceInventoryManagement | serviceCreateEvent, serviceAttributeValueChangeEvent, serviceStateChangeEvent, serviceDeleteEvent | Partially wired (self-listener scaffolding) | `/tmfc008/listener/serviceInventory` accepts TMF638 self-events and routes them to `tmfc008.wiring.tools.handle_service_event()`. Handler remains log-only; core TMF638 publication is handled by `tmf.service`. |
| TMF633 | ServiceCatalogManagement | serviceSpecificationDeleteEvent | Wired (dependency linkage) | `/tmfc008/listener/serviceCatalog` delegates to `tmfc008.wiring.tools.handle_service_spec_event()`, which resolves the referenced `tmf.service.specification` and, where `tmf.service.product_specification_id` already points at that spec, records a ServiceSpecificationRef in `tmfc008_service_spec_ref_json` and adds the spec to `tmfc008_service_specification_ids`. No master data is created or deleted. |
| TMF669 | PartyRoleManagement | partyRoleDeleteEvent | Partially wired (conservative linkage) | `/tmfc008/listener/partyRole` delegates to `tmfc008.wiring.tools.handle_party_role_event()`, which, when the PartyRole and underlying Party can be resolved, links the role into `tmfc008_party_role_ids` for Services whose `partner_id` matches the Party. Behaviour is additive and does not alter base Party/PartyRole models. |
| TMF674 | GeographicSiteManagement | geographicSiteDeleteEvent | Not evidenced | No ServiceInventory listener or geo linkage exists; any future `place` references on `tmf.service` will need delete-event reconciliation. Geo wiring remains out of scope for TMFC008 pass 2. |
| TMF675 | GeographicLocation | geographicLocationDeleteEvent | Not evidenced | As above; no current geographicLocation wiring on ServiceInventory. Geo wiring remains out of scope for TMFC008 pass 2. |
| TMF632 | PartyManagement | individualDeleteEvent, organizationDeleteEvent | Wired (dependency linkage) | `/tmfc008/listener/party` delegates to `tmfc008.wiring.tools.handle_party_event()`, which resolves the Party to `res.partner` and, for any `tmf.service` records already owned by that partner, appends a RelatedPartyRef into `tmfc008_related_party_json` and links the partner in `tmfc008_related_partner_ids`. Underlying `partner_id` behaviour is unchanged. |
| TMF641 | ServiceOrderingManagement | serviceOrderDeleteEvent | Wired (dependency linkage) | `/tmfc008/listener/serviceOrder` delegates to `tmfc008.wiring.tools.handle_service_order_event()`, which resolves the ServiceOrder, inspects `serviceOrderItem[*].service` references, and for any matching `tmf.service` records records a ServiceOrderRef in `tmfc008_service_order_ref_json` and links the order in `tmfc008_service_order_ids`. |

### Implementation tasks (pass 1+2)
- [x] Confirm YAML-to-code mapping for TMF638/TMF701 exposed APIs (baseline `tmf_service_inventory` + shared `tmf_process_flow`).
- [x] Capture current dependent API evidence from existing modules (`tmf_service_inventory`, `tmf_resource_inventory`, `tmf_service_catalog`, `tmf_customer`, `tmf_party_role`, `tmf_geographic_*`, `tmf_service_order`).
- [x] Create `tmfc008_wiring` addon skeleton following the established side-car pattern (models, controllers, security, data).
- [x] Introduce raw TMF reference fields on `tmf.service` via `TMFC008ServiceWiring` for ServiceCatalog, ResourceInventory, Party/PartyRole, and ServiceOrder references.
- [x] Add relational fields to represent resolved dependencies (serviceSpecification/serviceSpecificationRef, supportingResource/resourceRefs, Party/PartyRole, serviceOrder) and optional TMF701 process/task-flow links without altering CTK payload shapes.
- [x] Implement TMFC008-specific hub façade route (`/tmfc008/hub/serviceInventory`) backed by `tmf.hub.subscription`.
- [x] Design and implement listener endpoints for TMF639, TMF633, TMF669, TMF632, TMF641 (and self-subscriptions) and wire `tmfc008.wiring.tools` to perform additive, best-effort reconciliation for ServiceCatalog/ResourceInventory/Party/PartyRole/ServiceOrder dependencies where local records already exist.
- [ ] Refine TMF638 event publication so that state-change vs attribute-change events are distinguishable where required by the YAML.
- [ ] Capture verification notes summarizing the ServiceInventory role in the product/service/resource chain (interactions with TMFC003, TMFC005, TMFC006, TMFC007).
- [ ] Update `TMFC_IMPLEMENTATION_STATUS.md` once the TMFC008 pass 2 wiring is fully verified.

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
- [x] Verification notes captured
- [x] `TMFC_IMPLEMENTATION_STATUS.md` updated after broader TMFC007 wiring pass

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
- [x] Capture verification notes summarizing cross-component interactions between TMFC003/TMFC005/TMFC006/TMFC007 and underlying TMF638/TMF652/TMF681/TMF697 domains.
- [x] Update `TMFC_IMPLEMENTATION_STATUS.md` once TMFC007 wiring matures beyond this pass.

#### Verification notes (TMFC003/TMFC005/TMFC006/TMFC007 over TMF638/652/681/697)
- TMF638 ServiceInventory: `tmf.service` instances created from `sale.order` (TMFC005/TMFC006) are linked back to ServiceOrders via `TMFC007ServiceOrderWiring.service_ids`, giving TMFC003/TMFC007 a shared ServiceInventory surface for orchestration without changing TMF641 payloads.
- TMF652 ResourceOrder: TMFC003 owns ResourceOrder↔ServiceOrder↔ProductOrder orchestration; TMFC007 listeners simply validate envelopes and forward events into `tmfc003.wiring.tools.handle_resource_order_event()`, so there is a single aggregation path for ResourceOrder state.
- TMF681 CommunicationMessage: TMFC007 extends `tmf.communication.message` with JSON + relational ServiceOrder links and reconciles `state` from TMF681 events; Product/Service orchestration components can traverse Communication→ServiceOrder→Service without duplicating wiring.
- TMF697 Work/WorkOrder: `tmf.work` acts as the local WorkOrder representation. TMFC007 wiring attaches ServiceOrder refs and reconciles `tmf.work.state` from WorkOrder events, so any TMF701 flows or workforce processes can navigate Work→ServiceOrder consistently.

---

[... remaining sections (backlog, verification strategy) unchanged ...]
