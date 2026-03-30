# UI Generator Defaults for OdooTMFOpenAPI

## Purpose

This document defines the minimum default output expected from any generator or regeneration pipeline that emits Odoo views for TMF modules.

The project currently contains many `generated_views.xml` files, but no obvious single in-repo generator/template source was found during the audit. Because of that, this document serves as the **contract** the generator layer should follow when it is located or refactored.

---

## Problem Statement

Historically, generated views have tended to produce:
- list + form only
- weak or missing search UX
- raw payload-first forms
- no action help
- incomplete or inconsistent menu/action wiring
- overexposure of API-native naming in the UI

This causes the UI to be generator-first instead of user-first.

---

## Required Default Output Per User-Facing Model

Every generated user-facing model must include:

1. tree/list view
2. form view
3. search view
4. `ir.actions.act_window`
5. reachable `menuitem`
6. action help text

If any of these are missing, the generated module is incomplete.

---

## Default Tree/List Template

### Include by default
- primary identifier (`name` if available, otherwise TMF id)
- TMF ID
- core status/state
- key relationship field (partner/customer if present)
- key type/category field if present
- primary date field if present

### Rules
- do not include raw JSON/Text payload fields in tree views
- use badge widgets for status/state where appropriate
- mark secondary columns as `optional="show"` or `optional="hide"`
- keep lists scannable

### Preferred column priority order
1. Name / Title
2. TMF ID
3. Customer / Party
4. State / Status
5. Type / Category
6. Primary Date

---

## Default Search Template

### Search fields
Add fields when present on the model:
- TMF ID
- Name / Description
- Partner / Customer
- Type / Category
- State / Status
- Primary date field

### Default filters
At minimum, generate:
- Recent
- With related party / customer (if relation exists)
- status/state filters for common states

### Default group-by filters
Generate plain `filter` entries with `context={'group_by': ...}` for:
- state/status
- partner/customer
- category/type
- primary date

### Odoo 19 compatibility note
Avoid using search-view wrapper constructs that may fail validator compatibility in this project environment.
Use simple, flat search structures.

Preferred safe pattern:
- direct `<field/>`
- direct `<filter/>`
- optional `<separator/>`

Avoid relying on advanced wrapper/group structures unless validated in this environment.

---

## Default Form Template

Every major generated form should use a notebook structure.

### Standard pages
1. **General**
2. **Relationships**
3. **Lifecycle / Status**
4. **Commercial / Operations** (only when relevant)
5. **Technical / Payload**

### General page should prioritize
- business identity
- core relationships
- lifecycle summary
- key dates

### Technical / Payload page should contain
- JSON payload fields
- low-level integration structures
- API-native nested objects
- debug content

### Rule
Payload fields must not dominate the top of the form.

---

## Default Action Template

Every generated action must include:
- `name`
- `res_model`
- `view_mode="list,form"`
- `search_view_id`
- contextual `help`

### Help text pattern
```xml
<field name="help" type="html">
  <p class="o_view_nocontent_smiling_face">Create your first record</p>
  <p>Manage [business concept], related entities, lifecycle state, and technical payload details from this screen.</p>
</field>
```

The help text should be business-aware, not generic.

---

## Default Menu Template

Every generated module should have a reachable menu path.

### Rules
- place the module under an explicit domain root
- do not rely on runtime normalization as the primary grouping mechanism
- menu hierarchy should be meaningful before post-install normalization

### Preferred pattern
- domain root menu
- one child leaf menu per main model/action

---

## Labeling Rules

### Backend names may remain API-native
Field technical names can remain aligned with TMF/OAS naming.

### UI labels should be user-facing
When generating visible strings, prefer:
- `TMF ID`
- `Qualification Date`
- `Qualification Result`
- `Related Party`
- `Product Payload`
- `Technical / Payload`

Avoid exposing raw API names as visible labels when a better user-facing string exists.

---

## Relationship Handling Defaults

When relational helper fields exist, surface them before raw JSON.

Examples:
- `partner_id` before `related_party_json`
- `product_tmpl_id` before `product_json`
- `sale_order_id` before raw order payload fields

This supports operator workflows while still preserving full API data.

---

## Inheritance Rules for Generated Base Forms

Generated forms should be inheritance-friendly.

### Therefore
- always include a single `notebook` for major forms
- avoid fragmented or deeply nested structural patterns
- provide stable insertion points for module extensions

This makes downstream custom modules easier to maintain.

---

## Minimal Compliance Checklist for Generated Views

A generated view set is compliant only if:

- [ ] there is a reachable action and menu
- [ ] there is a dedicated search view
- [ ] there is meaningful action help
- [ ] the form is notebook-based for major models
- [ ] JSON payloads are isolated in a technical area
- [ ] list view is business-readable
- [ ] the search view supports operational filtering and grouping
- [ ] labels are reasonably user-facing
- [ ] generated XML is compatible with the target Odoo validator

---

## Immediate Recommendation

When the generator source is identified, apply this contract first to:
- service inventory patterns
- qualification patterns
- account patterns
- quote patterns

These four are the best reference families for broad reuse.

---

## Architectural Principle

Do not keep repairing generated output forever.
Push the design standard into the generation layer so consistency is created at source.
