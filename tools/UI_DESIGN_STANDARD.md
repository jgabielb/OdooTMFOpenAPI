# UI Design Standard for OdooTMFOpenAPI

## Purpose

This document defines the UI/UX rules for OdooTMFOpenAPI modules.

The goal is to ensure the product is:

- business-facing, not payload-facing
- navigable at scale
- consistent across modules
- maintainable in source XML
- less dependent on runtime UI repair logic

---

## Core Principle

The UI must present **business workflows first** and **API payloads second**.

Every major screen should help the user answer, in this order:

1. What is this record?
2. What state is it in?
3. Who/what is it related to?
4. What are the key business fields?
5. What are the technical/debug payload details?

If a screen starts with raw JSON or API-native payload structures, it is exposing implementation detail instead of product meaning.

---

## Canonical Navigation Structure

Top-level navigation should be explicitly declared in XML and organized into domain buckets.

### 1. Catalog
- Product Catalog
- Product Offering
- Service Specification
- Resource Specification

### 2. Party / Customer / Account
- Party
- Customer
- Account
- Billing Account
- Customer Bill
- Balance / Payment / Usage

### 3. Commercial
- Quote
- Promotion
- Recommendation
- Sales / Revenue Sharing

### 4. Ordering / Qualification
- Product Order
- Service Order
- Product Offering Qualification
- Service Qualification

### 5. Inventory / Resource / Service
- Resource Inventory
- Resource Pool
- Service Inventory
- Activation / Configuration

### 6. Assurance / Operations
- Trouble Ticket
- Alarm
- Performance
- Quality
- Test / Test Execution

### 7. Webhooks / Events
- Hub Subscriptions
- Event Management

### 8. Technical / Admin
- Wiring / Mapping
- Role / Permission
- Internal Integration / Debug

### Rule
This structure should live primarily in source XML. Runtime regrouping should be a fallback, not the primary architecture.

---

## Required View Set Per User-Facing Model

Every important model should define:

1. tree/list view
2. form view
3. search view
4. window action
5. menu binding

Optional where useful:
- kanban
- graph
- pivot
- activity/chatter

If a user-facing model lacks any of the first five, the module is UX-incomplete.

---

## Standard List View Rules

### Purpose
List views must support:
- scanning
- comparison
- filtering
- fast entry into records

### Standard columns
Prefer the following core columns where relevant:
- Name / Title
- TMF ID
- State / Status
- Type / Category
- Customer / Related Party
- Create Date / Last Update
- Company (if relevant)

### Rules
- Keep lists readable on first screen width
- Avoid raw JSON fields in list views
- Limit default columns to the most meaningful fields
- Use state badges/decorations where useful
- Avoid technical payload dumps in lists

---

## Standard Search View Rules

Search views are mandatory for major operational models.

### Standard searchable fields
- name
- tmf_id
- state / status
- partner / customer
- external id (if relevant)
- create/update dates

### Standard filters
At minimum, define context-appropriate filters such as:
- Draft / Pending
- Open / In Progress
- Done / Closed / Completed
- Failed / Error
- Recent records
- My records (where assignment matters)

### Standard group-by
- State / Status
- Customer / Party
- Type / Category
- Create Month / Update Month
- Assigned User / Team (if relevant)

### Examples by domain
#### Service Inventory
Filters:
- Active
- Inactive
- Suspended
- With Resource
- With Specification

Group by:
- State
- Category
- Customer
- Service Type

#### Product Offering Qualification
Filters:
- In Progress
- Qualified
- Unqualified
- Recent

Group by:
- State
- Result
- Product Offering
- Qualification Date

#### Trouble Ticket
Filters:
- Open
- Closed
- Escalated
- High Priority

Group by:
- Status
- Severity
- Customer
- Channel

---

## Standard Form Layout

Use notebook-based forms for all major models.

### Recommended tabs
#### 1. General
Main business identity and summary:
- name
- tmf_id
- description
- type/category
- core business fields

#### 2. Relationships
References to:
- customer/party
- orders
- services/resources
- offerings/specifications
- upstream/downstream entities

#### 3. Lifecycle / Status
- state
- status
- qualification result
- operating status
- priority / severity
- relevant dates

#### 4. Commercial / Operations
Where relevant:
- pricing
- billing
- usage
- SLA/SLO data
- commitments

#### 5. Technical
- external IDs
- integration metadata
- hub/webhook references
- system references

#### 6. Raw Payload / Debug
- raw_json
- request_json
- response_json
- generated payloads

### Rule
Raw payload fields must not dominate the first screen. They belong in the last technical/debug tab.

---

## Standard Header Rules

Headers should represent workflow, not miscellaneous actions.

### Use in headers
- statusbar widget
- business workflow transitions
- clear operational buttons

### Good examples
- activate
- suspend
- approve
- qualify
- close
- retry sync

### Avoid
- too many technical buttons in header
- unrelated debug actions mixed with lifecycle actions
- duplicative buttons that do not reflect workflow state

Header = workflow cockpit.
Sheet = record detail.

---

## Labels and Wording Rules

UI labels should be user-facing even if model field names remain API-native.

### Prefer
- Qualification Date
- Related Party
- Operating Status
- Service Specification
- Raw Payload

### Avoid exposing directly to end users
- productOfferingQualificationDate
- related_party_json
- serviceLevelObjectiveParameter
- test_environment_allocation_execution_json

The backend can speak API. The UI should speak user.

---

## Action Help and Empty-State Rules

Every important action should define explicit help text.

### Help text should explain
- what the screen manages
- what the records mean
- how the user typically starts

### Preferred style
Instead of generic text like:
- "Create a new record"

Prefer domain-aware help like:
- "Manage Service Inventory records. Track lifecycle state, linked specifications, supporting resources, and customer relationships from this screen."

---

## XML Inheritance Rules

### Prefer
- inserting into existing notebook/page structures
- inserting into existing named groups
- precise XPath expressions
- minimal structural changes

### Avoid
- creating a second notebook when the base form already has one
- duplicating headers/sheets/notebooks
- brittle XPath patterns tied to unstable positions

### Principle
Extend the UI like a surgeon, not like a bulldozer.

---

## Generator / Template Requirements

The generator layer should produce by default:

- tree view
- form view
- search view
- action
- menu
- contextual help text
- notebook structure
- standard header/status behavior
- technical/debug tab
- standard search filters and group-by options

### Strategic rule
Do not hand-fix 100 modules forever.
Fix the generator/templates so future modules are born consistent.

---

## Role of UI Normalizer

### Keep as temporary guardrail
The UI normalizer can still help with:
- legacy naming cleanup
- compatibility fixes
- minor post-install polish

### But it should not be the source of truth for
- primary information architecture
- menu grouping strategy
- action help authorship
- compensation for missing search views
- compensation for poor form design

### Long-term goal
Move UI design decisions into source-controlled XML and generator templates.
Keep UI normalization as a lightweight enforcement layer, not the main architect.

---

## Practical Quality Checklist

Before accepting a module UI, verify:

- [ ] It has list, form, search, action, and menu
- [ ] Menu opens a meaningful action
- [ ] Search view has useful filters and group-by
- [ ] List view shows business-critical columns only
- [ ] Form opens with business meaning, not raw payload
- [ ] Raw JSON is isolated in Technical / Debug tab
- [ ] State/status is visible and workflow-oriented
- [ ] Labels are user-facing
- [ ] Help text is domain-aware
- [ ] XML inheritance is clean and non-fragmenting
- [ ] UI behavior does not depend primarily on runtime normalization

---

## Final Principle

A good enterprise UI is not just a mirror of the API.
It is a decision-making surface for operators, analysts, and business users.

Design for comprehension first, then for completeness.
