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
- [ ] Verification notes captured for full TMFC surface (including TMF671/TMF701)
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

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
- [ ] Capture verification notes

---

## TMFC002 – ProductOrderCaptureAndValidation

**Status:** In analysis
**Target sprint:** Sprint 1
**Current classification:** Partially wired
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
- [ ] Verification notes captured
- [ ] `TMFC_IMPLEMENTATION_STATUS.md` updated after implementation pass

### Implementation tasks
- [x] Confirm YAML-to-code mapping for TMF648 exposed APIs
- [x] Confirm YAML-to-code mapping for TMF663 exposed APIs
- [ ] Confirm YAML-to-code mapping for TMF701 exposed APIs
- [ ] Verify dependent references beyond current Party/Offering/Billing/POQ/SQ/Cart links
- [x] Verify event publication for order/cart flows
- [x] Verify subscribed-event handling for TMF679/TMF673/TMF676/TMF716 (at least ProductOrder listener coverage)
- [ ] Capture verification notes

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
- [ ] Integration smoke test: POST sale.order inProgress → verify service order spawn + flow creation

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

## Backlog TMFCs to expand next

These still need to be converted from YAML summaries into execution checklists:
- TMFC006
- TMFC007
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
