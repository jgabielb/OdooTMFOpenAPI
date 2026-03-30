# UI Remediation Wave 1

## Purpose

This document defines the first implementation wave for UI improvements in OdooTMFOpenAPI.

It translates the UI design standard into concrete module-level work, starting with the highest leverage areas.

---

## Wave 1 Goals

1. make the core operational modules navigable and searchable
2. shift forms from API-first to business-first
3. reduce dependency on runtime UI normalization
4. establish reusable reference patterns for later modules

---

## Priority Modules

### 1. tmf_service_inventory
### Why
- central operational entity
- already one of the cleaner modules
- ideal candidate to become a reference implementation

### File targets
- `tmf_service_inventory/views/tmf_service_views.xml`
- related menu/action XML if split elsewhere
- `tmf_service_inventory/models/tmf_service.py` only if field labels need cleanup at source level

### Problems to solve
- no strong search UX
- form still too close to technical/API structure
- relationships are not surfaced as clearly as they should be
- v4/v5 serializer lessons should not leak confusing fields into the UI

### Required improvements
#### Navigation
- verify menu/action reachability
- add contextual action help

#### Search view
Add a dedicated search view with:
- Name
- TMF ID
- State
- Service Type
- Category
- Customer / Related Party
- Service Date

Filters:
- Active
- Inactive
- Suspended
- With Specification
- With Supporting Resource
- Recent

Group by:
- State
- Category
- Customer
- Service Type

#### Form redesign
Organize into tabs:
- General
- Relationships
- Lifecycle / Status
- Technical
- Raw Payload / Debug

Main page should show:
- name
- tmf_id
- state
- operating status
- customer
- specification
- resource
- service type
- category

#### List redesign
Default list columns:
- Name
- TMF ID
- State
- Operating Status
- Category
- Customer
- Service Date

### Target outcome
Reference standard for inventory/service UX.

---

### 2. tmf_product_offering_qualification
### Why
- core user-facing operational workflow
- important decision screen
- good place to define a business-first qualification UX standard

### File targets
- `tmf_product_offering_qualification/views/generated_views.xml`
- inherited views such as wiring customizations
- especially check `tmfc027_wiring/views/wiring_views.xml`

### Problems to solve
- weak search UX
- form structure likely too technical
- inheritance quality risk in wiring extensions
- qualification result and lifecycle not surfaced strongly enough

### Required improvements
#### Navigation
- verify action/menu/help consistency

#### Search view
Add searchable fields:
- Name / Description if meaningful
- TMF ID
- State
- Qualification Result
- Product Offering / Item reference
- Qualification Date
- Related Party

Filters:
- In Progress
- Qualified
- Unqualified
- Recent
- With Related Party

Group by:
- State
- Qualification Result
- Qualification Date
- Product Offering
- Related Party

#### Form redesign
Tabs:
- General
- Request / Qualification Context
- Result
- Relationships
- Technical
- Raw Payload / Debug

#### Inheritance cleanup
- stop adding parallel notebook structures where base form already has one
- inject pages into the existing notebook instead

### Target outcome
Reference standard for order/qualification UX.

---

### 3. tmf_account
### Why
- high business value area
- currently a strong example of JSON-heavy UI exposure
- ideal for proving how to separate business and technical information

### File targets
- `tmf_account/views/generated_views.xml`
- associated model field strings where needed

### Problems to solve
- raw JSON fields too prominent
- no curated search UX
- likely weak grouping for financial/party use cases

### Required improvements
#### Search view
Search fields:
- Name
- TMF ID
- Status
- Account Type
- Related Party
- Create Date

Filters:
- Active
- Suspended
- Recent
- With Related Party

Group by:
- Status
- Account Type
- Related Party
- Create Month

#### Form redesign
Tabs:
- General
- Party / Relationships
- Financial / Billing
- Lifecycle / Status
- Technical
- Raw Payload / Debug

#### Cleanup rule
JSON-style fields should move out of primary form body.

### Target outcome
Reference standard for account/customer-facing financial screens.

---

### 4. tmf_service_quality_management
### Why
- concrete UI wiring problems already identified
- likely under-usable despite having supporting models/actions

### File targets
- `tmf_service_quality_management/views/menu.xml`
- `tmf_service_quality_management/views/actions.xml`
- `tmf_service_quality_management/views/service_level_objective_views.xml`
- any sibling SLS/subscription view files

### Problems to solve
- menu/action mismatch
- dead or incomplete navigation
- no search views
- technical fields too exposed

### Required improvements
#### Fix first
- ensure each leaf menu points to the correct action
- ensure every action opens a coherent list/form/search flow

#### Search views
For SLO/SLS models add:
- Name
- TMF ID
- State / Status
- Related Service / Spec if relevant
- Create Date

Filters:
- Active
- Inactive
- Recent

Group by:
- Status
- Type
- Create Month

#### Form redesign
Tabs:
- General
- Parameters
- Relationships
- Lifecycle / Status
- Technical
- Raw Payload / Debug

### Target outcome
Moves from code-defined to user-operable.

---

### 5. tmf_quote_management
### Why
- commercially important
- currently not exposed clearly enough
- should become part of a coherent commercial workflow with qualification and ordering

### File targets
- `tmf_quote_management/views/tmf_quote_views.xml`
- associated action/menu XML if missing or split elsewhere

### Problems to solve
- incomplete reachability
- unclear workflow surfacing
- likely missing search UX

### Required improvements
#### Navigation
- ensure quote screens are reachable from menu/action
- add action help text

#### Search view
Search fields:
- Quote Name
- TMF ID
- State
- Customer
- Related Offering / Product
- Create Date

Filters:
- Draft
- In Progress
- Approved
- Rejected
- Recent

Group by:
- State
- Customer
- Create Month

#### Form redesign
Tabs:
- General
- Customer / Relationships
- Commercial Details
- Lifecycle / Approval
- Technical
- Raw Payload / Debug

### Target outcome
Commercial workflow reference screen.

---

## Cross-Cutting Rules for Wave 1

For all five modules:

### Required deliverables
- explicit search view
- contextual action help
- notebook-based form structure
- technical/debug isolation
- cleaner list columns
- reachable menu/action path

### Nice-to-have if cheap
- better statusbar presentation
- badge/decorated list fields
- smarter default ordering

---

## Execution Sequence Per Module

### Phase A — Navigation integrity
- verify menu exists
- verify action exists
- verify action points to usable views
- add domain-specific help text

### Phase B — Search UX
- define search view
- define filters
- define group-by
- verify usability with realistic record counts

### Phase C — Form redesign
- introduce notebook tabs
- move raw JSON to technical/debug tab
- keep business summary at top

### Phase D — Label cleanup
- humanize labels
- reduce raw API wording where visible to users

### Phase E — Generator feedback loop
- identify what should be moved into generator templates

---

## Suggested Sprint Breakdown

### Sprint 1
- `tmf_service_inventory`
- `tmf_product_offering_qualification`

### Sprint 2
- `tmf_account`
- `tmf_service_quality_management`

### Sprint 3
- `tmf_quote_management`
- then secondary cleanup of:
  - `tmf_user_role_permission`
  - `tmf_recommendation_management`

### Sprint 4
- push repeated improvements into generator/template layer

---

## Success Criteria

Wave 1 is successful if:

- each target module is reachable and understandable without technical knowledge
- major records can be found quickly via search/filter/group-by
- raw payload fields no longer dominate the primary form experience
- menu/action behavior is predictable in XML, not mostly repaired at runtime
- the first two improved modules become reusable design references

---

## Recommended First Build Pair

If implementation starts immediately, begin with:

1. `tmf_service_inventory`
2. `tmf_product_offering_qualification`

These two give the best architectural return because they define the patterns for:
- operational inventory UX
- qualification/workflow UX

Use them as the template pair for the rest of the repo.
