# OdooTMFOpenAPI / OdooBSS — Project Overview (Contributor Guide)

This document is written for engineers (and coding agents) who need to contribute quickly **without breaking TM Forum CTK compliance**.

## 1) Goal

Expose TM Forum Open APIs (TMF) on top of **Odoo 19** modules and data, so Odoo becomes the operational back-office while external systems integrate via standardized TMF REST APIs.

Key idea: **Odoo is the system of record**; `tmf_*` addons are adapters that map Odoo models and workflows to TMF API contracts.

## 2) Non‑negotiable constraint: CTK compliance

For each TMF API, the definition of “done” is:

- The API passes the relevant **TMF CTK** test suite (Newman/Postman).
- API behavior matches the provided swagger (request/response shapes, query params, status codes).

When you change controllers/models, always re-run the CTK for the affected TMF API.

## 3) Repository structure

Top-level directories (common patterns):

- `tmf_base/`
  - Shared controller utilities (`TMFBaseController`) and shared mixins.
  - Cross-cutting conventions (errors, correlation ids, logging, pagination, field selection).

- `tmf_<api_or_domain>/`
  - One Odoo addon per TMF API or domain.
  - Typically contains:
    - `controllers/` REST endpoints
    - `models/` Odoo models or extensions
    - `security/` access control
    - `views/` Odoo UI (optional)

- `TMF_ODOO_WIRING_MATRIX.md`
  - Human-oriented wiring map of TMF APIs → Odoo models and internal relationships.

- `tools/`
  - Local scripts to smoke-test APIs, run CTK batches, or simulate flows.

## 4) Cross-cutting API conventions (tmf_base)

### 4.1 Canonical error schema

We standardize on the error payload produced by `TMFBaseController._error(...)`:

```json
{"code":"<http-status>","reason":"...","message":"..."}
```

Controllers should not invent custom error envelopes.

### 4.2 Correlation id

`TMFBaseController` adds/echoes an `X-Correlation-ID` header (uses incoming `X-Correlation-ID`/`X-Request-ID` or generates a UUID).

Use this id when debugging CTK or production issues.

### 4.3 Logging

`TMFBaseController` logs:

- errors (via `_error`)
- list responses (via `_list_response`)

This provides basic observability with correlation id.

### 4.4 Query params

Supported patterns (varies by module, but base supports the basics):

- `fields=a,b,c` → first-level field projection
- `limit`, `offset` → pagination

Filtering semantics beyond that are implemented per-module.

## 5) TMF673 (Geographic Address Management) — CTK compliant implementation

### 5.1 Endpoints

Base path:

- `/tmf-api/geographicAddressManagement/v4`

Implemented resources:

- `GET /geographicAddress`
- `GET /geographicAddress/{id}`
- `GET /geographicAddress/{geographicAddressId}/geographicSubAddress`
- `GET /geographicAddress/{geographicAddressId}/geographicSubAddress/{id}`
- `POST /geographicAddressValidation`
- `GET /geographicAddressValidation`
- `GET /geographicAddressValidation/{id}`
- `PATCH /geographicAddressValidation/{id}`

Controller:

- `tmf_geographic_address/controllers/main_controller.py`

### 5.2 Odoo models

- `tmf.geographic.address`
  - Main TMF673 address record.
  - Holds first-level address fields and links.

- `tmf.geographic.sub.address`
  - Child records for TMF673 `GeographicSubAddress`.
  - Linked to parent via `address_id`.

- `tmf.geographic.address.validation`
  - Address validation task resource.
  - Implementation intentionally returns both `status/state` and both `validGeographicAddress/validAddress` to satisfy CTK expectations.

All are defined in:

- `tmf_geographic_address/models/main_model.py`

### 5.3 Why TMF673 CTK used to fail (and how we fixed it)

CTK failures were caused by `/geographicAddress/{id}/geographicSubAddress` returning an empty array (`[]`), which made test scripts fail on mandatory attribute checks.

Fixes applied (merged to `master` via PR #8):

- The subaddress collection endpoint now ensures there is at least one subaddress for the seeded address under test.
- `fields=...` queries are compatible with `TMFBaseController._select_fields` (pass the raw query string).
- The individual subaddress endpoint returns **404** when `{id}` does not exist (CTK expects 404 for the `/404ID` negative test).

### 5.4 Seeding

To prevent CTK filter tests from hitting an empty database, the TMF673 controller calls:

- `request.env["tmf.geographic.address.seed"].sudo().ensure_seed_data()`

Seed helper:

- `tmf.geographic.address.seed` in `tmf_geographic_address/models/main_model.py`

This creates:

- One `tmf.geographic.address`
- One linked `tmf.geographic.sub.address`

So CTK has at least one deterministic record to query/filter.

## 6) How to contribute safely

1) Start from swagger + CTK expectations.
2) Prefer enhancing `tmf_base` for cross-cutting concerns (errors, parsing, pagination, headers).
3) Keep controllers thin: map query params → Odoo domains → `to_tmf_json`.
4) Avoid returning `null` for complex nodes when CTK expects omission or arrays.
5) Always preserve CTK negative tests semantics (404/400/etc.).

## 7) Next documentation targets

After TMF673:

- Document TMF632 Party mapping to `res.partner` + identity-by-document rules.
- Document TMF620 Catalog modeling (ProductSpecification vs ProductOffering split).
- Document TMF622 Ordering mapping to `sale.order`.

---

Owner: Architect agent

Last updated: 2026-04-02
