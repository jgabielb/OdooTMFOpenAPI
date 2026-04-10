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

[... remaining sections (TMFC007, backlog, verification strategy) unchanged ...]
