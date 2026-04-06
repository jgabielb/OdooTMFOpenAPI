# TMFC Wiring Delivery Plan — OdooBSS

This plan turns the ODA/TMFC gap analysis into an executable delivery roadmap.

It is intentionally organized around **repeatable wiring work**, not just around API availability.
For a TMFC to be considered done, we need evidence for:

1. **Exposed APIs** mapped from TMFC YAML to Odoo modules/controllers
2. **Dependent API wiring** implemented through side-car `tmfc*_wiring` patterns or equivalent
3. **Published events** evidenced in models/controllers/hub registration
4. **Subscribed events** evidenced by listener endpoints, callback handling, and state update logic
5. **Documentation updated** in:
   - `docs/TMFC_WIRING_CHECKLIST.md`
   - `docs/TMFC_IMPLEMENTATION_STATUS.md`

---

## 1. Delivery Principles

### 1.1 Architectural approach

We will use the existing successful side-car pattern already present in the repo:
- keep CTK-facing TMF APIs stable,
- add ODA-specific cross-component wiring in dedicated `tmfc*_wiring` addons,
- persist raw TMF reference fragments where useful,
- resolve references by `tmf_id` into relational Odoo links,
- avoid recursive writes using `skip_tmf_wiring`,
- keep event wiring explicit rather than implicit.

### 1.2 Definition of done per TMFC

A TMFC is only marked **fully wired** when all of the following are true:
- TMFC YAML has been reviewed and its required surface captured.
- All exposed APIs/resources are mapped to code.
- All key dependent APIs/resources are wired to local relations or orchestration logic.
- Published events required by the TMFC are actually emitted from mutation paths.
- Subscribed events required by the TMFC are actually received and processed.
- Status docs are updated with evidence-backed notes.
- Verification notes or lightweight test coverage exist for the component.

If only some of this is present, classify as **partially wired**.

---

## 2. Current Baseline

### 2.1 TMFCs with existing side-car wiring foundations

These already have `tmfc*_wiring` addons and should usually be completed before starting totally new ones:
- TMFC001 ProductCatalogManagement
- TMFC002 ProductOrderCaptureAndValidation
- TMFC005 ProductInventory
- TMFC020 DigitalIdentityManagement
- TMFC022 PartyPrivacyManagement
- TMFC023 PartyInteractionManagement
- TMFC027 ProductConfigurator
- TMFC028 PartyManagement
- TMFC031 BillCalculation

### 2.2 TMFCs without verified ODA wiring yet

These currently look like **TMF API present but ODA wiring missing**:
- TMFC003 ProductOrderDeliveryOrchestrationAndManagement
- TMFC006 ServiceCatalogManagement
- TMFC007 ServiceOrderManagement
- TMFC008 ServiceInventory
- TMFC009 ServiceQualificationManagement
- TMFC010 ResourceCatalogManagement
- TMFC011 ResourceOrderManagement
- TMFC012 ResourceInventory
- TMFC014 LocationManagement
- TMFC024 BillingAccountManagement
- TMFC029 PaymentManagement
- TMFC030 BillGeneration
- TMFC035 PermissionsManagement
- TMFC036 LeadAndOpportunityManagement
- TMFC037 ServicePerformanceManagement
- TMFC038 ResourcePerformanceManagement
- TMFC039 AgreementManagement
- TMFC040 ProductUsageManagement
- TMFC041 AnomalyManagement
- TMFC043 FaultManagement
- TMFC046 WorkforceManagement
- TMFC050 ProductRecommendation
- TMFC054 ProductTestManagement
- TMFC055 ServiceTestManagement
- TMFC061 WorkOrderManagement
- TMFC062 ResourceConfigurationandActivation

---

## 3. Sprint Plan

Assumption: **2-week sprints**.
If you want, this can later be translated into Jira, GitHub Projects, or Odoo project tasks.

---

## Sprint 0 — Foundations and tracking

### Goal
Create the delivery scaffolding so all TMFC work follows one repeatable method.

### Tasks
- [ ] Finalize the TMFC classification baseline in `TMFC_IMPLEMENTATION_STATUS.md`
- [ ] Expand `TMFC_WIRING_CHECKLIST.md` with per-TMFC sections for the first delivery wave
- [ ] Create a standard implementation checklist template for each TMFC:
  - YAML reviewed
  - exposed APIs mapped
  - dependent refs wired
  - published events verified
  - subscribed events implemented
  - verification notes captured
- [ ] Define naming convention for new wiring addons:
  - `tmfc003_wiring`
  - `tmfc006_wiring`
  - etc.
- [ ] Define verification strategy:
  - repo inspection
  - API smoke checks
  - event publication checks
  - callback/listener checks

### Deliverables
- Tracking docs in place
- Working template for future TMFC implementations

---

## Sprint 1 — Finish existing commerce foundations

### Goal
Complete the highest-value partially wired commerce components already started.

### TMFC scope
- TMFC001 ProductCatalogManagement
- TMFC002 ProductOrderCaptureAndValidation
- TMFC005 ProductInventory
- TMFC027 ProductConfigurator

### Tasks

#### TMFC001
- [ ] Verify and implement missing TMF620 resources:
  - [ ] catalog
  - [ ] category
  - [ ] importJob
  - [ ] exportJob
- [ ] Verify TMF671 promotion coverage against YAML
- [ ] Verify TMF701 processFlow/taskFlow coverage against YAML
- [ ] Implement/verify subscribed-event callbacks for:
  - [ ] TMF633 service specification/resource specification events
  - [ ] TMF632 individual/organization delete events
  - [ ] TMF669 party role delete events
- [ ] Update checklist + status docs

#### TMFC002
- [ ] Verify wiring coverage for TMF648/TMF663/TMF701 exposed APIs against YAML
- [ ] Implement missing dependent links from YAML where absent
- [ ] Verify qualification/reservation/address-driven callbacks and subscriptions
- [ ] Add event coverage notes and update docs

#### TMFC005
- [ ] Validate TMFC005 dependencies against YAML:
  - TMF620, TMF639, TMF638, TMF632, TMF669, TMF651, TMF666, TMF673/674/675, TMF622
- [ ] Implement missing cross-refs beyond stock location/lot/quant if needed
- [ ] Verify product inventory published/subscribed events
- [ ] Update docs

#### TMFC027
- [ ] Verify TMF760-specific needs, not only TMF679 wiring
- [ ] Add missing TMFC027 subscription handling for TMF622/TMF645 if absent
- [ ] Review intent/entity/billing/account/address coverage end to end
- [ ] Update docs

### Exit criteria
At least 2 of these TMFCs move from ⚠️ to ✅, and the rest have concrete residual gaps documented.

---

## Sprint 2 — Order-to-service orchestration backbone

### Goal
Build the missing ODA backbone between product order, service order, and resource order domains.

### TMFC scope
- TMFC003 ProductOrderDeliveryOrchestrationAndManagement
- TMFC007 ServiceOrderManagement
- TMFC011 ResourceOrderManagement
- TMFC062 ResourceConfigurationandActivation

### Tasks

#### TMFC003
- [ ] Create `tmfc003_wiring`
- [ ] Map TMFC003 YAML exposed APIs to existing modules
- [ ] Resolve dependencies between:
  - TMF622 product order
  - TMF633 service catalog
  - TMF638 service inventory
  - TMF641 service order
  - TMF634 resource catalog
  - TMF639 resource inventory
  - TMF652 resource order
  - TMF701 process flow
- [ ] Implement orchestration relations and callback processing for TMF641/TMF652 subscribed events
- [ ] Add tracking/docs

#### TMFC007
- [ ] Create `tmfc007_wiring`
- [ ] Implement side-car relations from service order to service/resource/address/appointment/work order domains
- [ ] Verify published events from service order mutations
- [ ] Implement required subscribed-event consumers
- [ ] Update docs

#### TMFC011
- [ ] Create `tmfc011_wiring`
- [ ] Wire resource order to resource inventory/catalog/pool/activation and geography/party references
- [ ] Implement subscription handling for TMF664/TMF702 events
- [ ] Update docs

#### TMFC062
- [ ] Create `tmfc062_wiring`
- [ ] Wire TMF702/TMF664 to TMF634/TMF639 references
- [ ] Verify activation/configuration event coverage
- [ ] Update docs

### Exit criteria
A coherent product-order to service-order to resource-order implementation path exists in Odoo side-car wiring. 🏛️

---

## Sprint 3 — Catalog and inventory backbone

### Goal
Complete the shared catalog and inventory components that many other TMFCs depend on.

### TMFC scope
- TMFC006 ServiceCatalogManagement
- TMFC008 ServiceInventory
- TMFC010 ResourceCatalogManagement
- TMFC012 ResourceInventory
- TMFC014 LocationManagement

### Tasks

#### TMFC006
- [ ] Create `tmfc006_wiring`
- [ ] Wire TMF633/TMF657 exposed resources to dependent TMF634/TMF632/TMF669/TMF662 refs
- [ ] Implement missing subscribed-event handling from TMF634/TMF662
- [ ] Update docs

#### TMFC008
- [ ] Create `tmfc008_wiring`
- [ ] Wire service inventory to service specification, resource inventory, party, geography, and service-order refs
- [ ] Implement delete/change subscriptions required by YAML
- [ ] Update docs

#### TMFC010
- [ ] Create `tmfc010_wiring`
- [ ] Wire resource catalog to party/entity references
- [ ] Implement TMF662/TMF669/TMF632 subscription handling
- [ ] Update docs

#### TMFC012
- [ ] Create `tmfc012_wiring`
- [ ] Wire resource inventory to resource specification, party, geography, pools, reservations
- [ ] Implement subscribed-event processing from TMF634/TMF639/TMF669/TMF632/TMF674/TMF675
- [ ] Update docs

#### TMFC014
- [ ] Create `tmfc014_wiring` only if needed for ODA component assembly
- [ ] Verify whether base geographic modules are enough or whether ODA-side event/listener packaging is missing
- [ ] Update docs

### Exit criteria
Catalog and inventory domains become reusable foundations for the remaining TMFCs.

---

## Sprint 4 — Party, account, payment, agreement, billing

### Goal
Complete customer/account-side cross-component wiring.

### TMFC scope
- TMFC020 DigitalIdentityManagement
- TMFC022 PartyPrivacyManagement
- TMFC023 PartyInteractionManagement
- TMFC024 BillingAccountManagement
- TMFC028 PartyManagement
- TMFC029 PaymentManagement
- TMFC030 BillGeneration
- TMFC031 BillCalculation
- TMFC039 AgreementManagement

### Tasks
- [ ] Finish partial TMFC020/TMFC022/TMFC023/TMFC028/TMFC031 gaps
- [ ] Create `tmfc024_wiring`
- [ ] Create `tmfc029_wiring`
- [ ] Create `tmfc030_wiring`
- [ ] Create `tmfc039_wiring`
- [ ] Implement event-driven relationships among party, account, agreement, payment, bill, and privacy domains
- [ ] Update docs

### Exit criteria
Customer/account/billing domains are wired consistently end to end.

---

## Sprint 5 — Commerce intelligence and lead flow

### Goal
Wire recommendation, usage, lead/opportunity, and permissions into the core commerce graph.

### TMFC scope
- TMFC035 PermissionsManagement
- TMFC036 LeadAndOpportunityManagement
- TMFC040 ProductUsageManagement
- TMFC050 ProductRecommendation

### Tasks
- [ ] Create `tmfc035_wiring`
- [ ] Create `tmfc036_wiring`
- [ ] Create `tmfc040_wiring`
- [ ] Create `tmfc050_wiring`
- [ ] Implement cross-links to Party, PartyRole, ProductCatalog, ProductInventory, ProductOrder, Billing, Usage
- [ ] Implement missing event subscriptions from upstream commerce domains
- [ ] Update docs

### Exit criteria
Commercial growth and recommendation flows are wired into the same graph as order, account, and product domains.

---

## Sprint 6 — Assurance and observability domains

### Goal
Wire performance, anomaly, and fault management into service/resource state changes.

### TMFC scope
- TMFC037 ServicePerformanceManagement
- TMFC038 ResourcePerformanceManagement
- TMFC041 AnomalyManagement
- TMFC043 FaultManagement

### Tasks
- [ ] Create `tmfc037_wiring`
- [ ] Create `tmfc038_wiring`
- [ ] Create `tmfc041_wiring`
- [ ] Create `tmfc043_wiring`
- [ ] Implement subscriptions from service/resource/catalog/location/alarm/problem domains
- [ ] Verify published management/notification events
- [ ] Update docs

### Exit criteria
Assurance components react to the operational graph instead of remaining isolated APIs.

---

## Sprint 7 — Test and workforce domains

### Goal
Close the operational support layer around tests, work orders, and workforce.

### TMFC scope
- TMFC046 WorkforceManagement
- TMFC054 ProductTestManagement
- TMFC055 ServiceTestManagement
- TMFC061 WorkOrderManagement

### Tasks
- [ ] Create `tmfc046_wiring`
- [ ] Create `tmfc054_wiring`
- [ ] Create `tmfc055_wiring`
- [ ] Create `tmfc061_wiring`
- [ ] Wire tests to product/service/resource entities and work execution flows
- [ ] Wire workforce/work-order dependencies and event subscriptions
- [ ] Update docs

### Exit criteria
Operational execution and testing flows are part of the overall ODA graph.

---

## Sprint 8 — Hardening and closure

### Goal
Move from “implemented” to “reliable and maintainable”.

### Tasks
- [ ] Review all TMFCs for consistency of naming, manifests, and dependency declarations
- [ ] Add missing verification scripts or smoke tests per implemented TMFC
- [ ] Normalize event naming and callback route coverage
- [ ] Remove placeholder/no-op wiring where real behavior is now required
- [ ] Final pass on `TMFC_WIRING_CHECKLIST.md`
- [ ] Final pass on `TMFC_IMPLEMENTATION_STATUS.md`
- [ ] Produce final architecture summary of the ODA implementation model

### Exit criteria
All targeted TMFCs are classified accurately, with documented evidence and maintainable side-car wiring patterns.

---

## 4. Task Board Template

Use this structure per TMFC when we start execution:

## TMFCxxx — <Name>
- Status: Not started | In progress | Blocked | Done
- Sprint: Sprint N
- Owner: Architect / Backend / QA
- YAML reviewed: Yes/No
- Exposed APIs mapped: Yes/No
- Dependent refs wired: Yes/No
- Published events verified: Yes/No
- Subscribed events implemented: Yes/No
- Docs updated: Yes/No
- Verification run: Yes/No
- Notes:
  - ...

---

## 5. Recommended execution order

If we want the most durable implementation path, the best order is:

1. Finish partially wired foundations first
   - TMFC001, TMFC002, TMFC005, TMFC027
2. Build orchestration backbone
   - TMFC003, TMFC007, TMFC011, TMFC062
3. Build shared catalog/inventory backbone
   - TMFC006, TMFC008, TMFC010, TMFC012, TMFC014
4. Build party/account/billing graph
   - TMFC020, TMFC022, TMFC023, TMFC024, TMFC028, TMFC029, TMFC030, TMFC031, TMFC039
5. Build commerce intelligence/supporting flows
   - TMFC035, TMFC036, TMFC040, TMFC050
6. Build assurance/test/workforce domains
   - TMFC037, TMFC038, TMFC041, TMFC043, TMFC046, TMFC054, TMFC055, TMFC061

This order reduces rework because later components depend on the graph established by earlier ones. That is the architectural equivalent of laying structural beams before painting rooms. 🏛️

---

## 6. Immediate next task

Start with **Sprint 0 + Sprint 1 / TMFC001**.

Why:
- TMFC001 is already partially wired,
- it is foundational for many downstream commerce components,
- finishing it will sharpen the template for all later TMFC implementations.

Immediate task list:
- [ ] Expand checklist entry for TMFC001 from YAML
- [ ] Verify missing TMF620 resources in code
- [ ] Implement missing subscribed-event handling
- [ ] Reclassify TMFC001 after code changes

---

## 7. Plan maintenance rules

Whenever we finish or materially change a TMFC:
- update this plan if sprint scope changes,
- update `TMFC_WIRING_CHECKLIST.md`,
- update `TMFC_IMPLEMENTATION_STATUS.md`,
- keep classifications evidence-based.

No TMFC should be marked complete just because its TMF API exists. The ODA value is in the wiring. 🏛️
