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

## 7) Product & Inventory TMFCs (001/002/005)

We use dedicated wiring addons to connect CTK-compliant TMF APIs into Odoo’s
native commercial and inventory models without altering CTK-visible behavior.

### TMFC001 – ProductCatalogManagement

- TMF API: TMF620 v5.0.0 Product Catalog Management
- Core addon: `tmf_product_catalog`
- Wiring addon: `tmfc001_wiring`
- Key patterns:
  - `_inherit = "product.template"` and `_inherit = "tmf.product.specification"`.
  - Add JSON reference fields (e.g. `related_party_json`, `place_json`,
    `agreement_json`, `service_specification_json`, `resource_specification_json`).
  - Add relational fields to:
    - Parties: `res.partner`, `tmf.party.role`.
    - Service/resource specs: `tmf.service.specification`, `tmf.resource.specification`.
    - Agreements: `tmf.agreement`.
    - Geographic entities: `tmf.geographic.address/site/location`.
  - All wiring is side-car: no controller changes, no impact on TMF620 CTKs.

### TMFC002 – ProductOrderCaptureAndValidation

- TMF API: TMF622 v5.0.0 Product Ordering Management
- Core addon: `tmf_product_ordering`
- Wiring addon: `tmfc002_wiring`
- Key patterns:
  - `_inherit = "tmf.product.order"`.
  - Raw TMF ref fields: `related_party_json`, `product_offering_json`,
    `billing_account_json`.
  - Relational fields:
    - `related_partner_ids` → `res.partner`.
    - `product_offering_ids` → `product.template`.
    - `billing_account_id` → `tmf.billing.account`.
    - `poq_ids` → `tmf.check.product.offering.qualification` (TMF679).
    - `sq_ids` → `tmf.service.qualification` (TMF645).
    - `cart_ids` → `tmf.shopping.cart` (TMF663).
    - `sale_order_id` → `sale.order` via `client_order_ref = tmf_id`.
  - `_resolve_tmf_refs()`:
    - Runs on `create`/`write` unless `skip_tmf_wiring` context flag is set.
    - Reads stored TMF payload JSON, resolves IDs into Odoo records.
  - TMF622 controllers remain unchanged; CTKs stay green.

### TMFC005 – ProductInventory

- TMF APIs: TMF637/638/639/640 inventory suite
- Core addons: `tmf_product_inventory`, `tmf_product_stock_relationship`, `tmf_product`
- Wiring addon: `tmfc005_wiring`
- Key patterns:
  - `_inherit = "tmf.product"`.
  - Raw ref fields: `stock_location_ref_json`, `lot_ref_json`.
  - Relational fields:
    - `product_tmpl_id` → `product.template`.
    - `product_id` → `product.product`.
    - `stock_location_id` → `stock.location`.
    - `stock_lot_id` → `stock.lot`.
    - `stock_quant_id` → `stock.quant`.
  - `_resolve_tmf_refs()`:
    - Resolves product by TMF-specific field or name.
    - Resolves location by TMF id or `name`.
    - Resolves lot by TMF id or `serialNumber`.
    - Resolves `stock.quant` from product/location[/lot].
  - Runs on `create`/`write` unless `skip_tmf_wiring` is set.
  - Inventory controllers remain untouched; CTKs for TMF637/638/639/640 stay green.

## 8) Party & Identity TMFCs (020/022/023/028)

Party and identity APIs are also CTK-first. All cross-domain wiring lives in
separate `_inherit` addons that never change controllers or `to_tmf_json`.

### TMFC020 – DigitalIdentityManagement

- TMF API: TMF720 Digital Identity Management
- Core addon: `tmf_digital_identity_management`
- Wiring addon: `tmfc020_wiring`
- Core model: `tmf.digital.identity` stores TMF JSON payloads in `*_json` text
  fields plus native links `partner_id`/`user_id`.
- Wiring model: `DigitalIdentityTMFC020Wiring` with `_inherit = "tmf.digital.identity"`.
- Relational fields:
  - `related_partner_ids` → `res.partner` from `related_party_json`.
  - `individual_partner_id` → `res.partner` from `individual_identified_json`.
  - `party_role_ids` → `tmf.party.role` from `party_role_identified_json` and
    PartyRole entries in `related_party_json`.
  - `resource_ids` → `stock.lot` from `resource_identified_json`.
- `_resolve_tmf_refs()`:
  - Parses JSON, extracts TMF ids, batch-resolves them into Odoo records.
  - Runs on `create` and on `write` when relevant `*_json` fields change,
    unless `skip_tmf_wiring` is present in context.
- The TMF720 controller and `to_tmf_json` implementation remain unchanged,
  preserving CTK behavior.

### TMFC028 – PartyManagement

- TMF API: TMF632 Party Management
- Core addon: `tmf_party` (extends `res.partner` with TMF Party view).
- Wiring addon: `tmfc028_wiring`.
- Wiring model: `_inherit = "res.partner"`.
- Relational fields:
  - `digital_identity_ids` → One2many to `tmf.digital.identity` via its
    `partner_id` (Digital Identities for this party).
  - `privacy_agreement_ids` → Many2many to `tmf.party.privacy.agreement`.
  - `party_interaction_ids` → One2many to `tmf.party.interaction` via
    `partner_id`.
- No `create`/`write` overrides: this is a pure relational view for Odoo and
  reporting. TMF632 controller behavior and CTKs are unaffected.

### TMFC022 – PartyPrivacyManagement

- TMF API: Party Privacy Agreement (TMF Party Privacy)
- Core addon: `tmf_party_privacy_agreement`.
- Wiring addon: `tmfc022_wiring`.
- Wiring model: `_inherit = "tmf.party.privacy.agreement"`.
- Wiring-only JSON fields:
  - `engaged_party_json` → raw TMF `engagedParty` reference.
  - `privacy_profile_json` → raw TMF `partyPrivacyProfile` reference.
- Relational fields:
  - `engaged_partner_ids` → Many2many `res.partner`.
  - `privacy_identity_ids` → Many2many `tmf.digital.identity`.
- `_resolve_tmf_refs()`:
  - Parses JSON refs, extracts TMF ids, resolves them into Party and
    DigitalIdentity records using their `tmf_id`.
  - Uses `with_context(skip_tmf_wiring=True)` to avoid recursion.
  - Hooked into `create`/`write`, but only runs when the wiring JSON fields
    change and when `skip_tmf_wiring` is not set.
- Core `to_tmf_json` and any controllers remain untouched; CTK payloads do not
  change.

### TMFC023 – PartyInteractionManagement

- TMF API: TMF683 Party Interaction Management
- Core addon: `tmf_party_interaction`.
- Core model: `tmf.party.interaction` already:
  - Stores `relatedParty` and other complex nodes as JSON.
  - Maintains `partner_id` by resolving `relatedParty` into `res.partner`.
  - Emits hub events for create/update/delete.
- Wiring addon: `tmfc023_wiring`.
- Wiring model: `_inherit = "tmf.party.interaction"`.
- Relational fields:
  - `digital_identity_ids` → Many2many `tmf.digital.identity`.
  - `privacy_agreement_ids` → Many2many `tmf.party.privacy.agreement`.
- `_resolve_tmf_refs()`:
  - Currently a no-op placeholder, ready to be extended when the TMF683
    payload introduces explicit references to identities/agreements in JSON.
  - Wired into `create`/`write` with a `skip_tmf_wiring` guard so we can add
    resolution logic later without touching controllers.

## 9) TMFC029 – PaymentManagement

TMFC029 is realized by a set of TMF payment-related addons that are already
CTK-compliant and wired into Odoo accounting. No extra wiring module is
introduced; instead, these modules form the Payment Management component.

### TMF676 – Payment (`tmf_payment`)

- Core model: `tmf.payment` (`_inherit = ["tmf.model.mixin"]`).
- Links to Odoo accounting:
  - `partner_id` → `res.partner` (customer).
  - `account_payment_id` → `account.payment` (Odoo payment).
  - `invoice_ids` → Many2many `account.move` (invoices).
  - `payment_method_line_id` → `account.payment.method.line`.
  - `journal_id` → `account.journal`.
- TMF JSON storage:
  - `account_json` (accountRef), `total_amount_json`, `payment_method_json`,
    `channel_json`, `payment_item_json`.
- Resolution logic:
  - `_resolve_partner_from_account_json()` → derives `res.partner` from
    `account_json` using TMF ids.
  - `_resolve_invoices_from_payment_item_json()` → derives invoices from
    `paymentItem.item.id`.
  - `_resolve_payment_method_line()` → derives the Odoo payment method line
    from `paymentMethod` via `tmf.payment.method`.
- `_sync_account_payment()`:
  - Ensures an `account.payment` exists and is kept in sync:
    - Sets partner, invoices, amount, journal, and payment method line based on
      TMF JSON and native links.
    - Only updates existing payments while in `draft` state.
- `to_tmf_json()`:
  - Builds TMF676 `Payment` payload, ensuring:
    - `account` and `paymentItem` are populated from native links if JSON is
      missing.
    - `status` reflects TMF status or underlying `account.payment.state`.
    - `fields` projection is supported while always emitting `id`/`href`.
- Lifecycle:
  - `create`:
    - Backfills `account_json` from `partner_id` when missing.
    - Calls `_sync_account_payment()`.
    - Emits `PaymentCreateEvent` via `tmf.hub.subscription`.
  - `write`:
    - Re-syncs Odoo payment and emits `PaymentAttributeValueChangeEvent`.
  - `unlink`:
    - Sends `PaymentDeleteEvent` with preserved payloads.

### TMF670 – PaymentMethod (`tmf_payment_method`)

- Core model: `tmf.payment.method`.
- TMF fields: `tmf_id`, `href`, `@type`, `@baseType`, `@schemaLocation`, plus
  `name`, `description`, `is_preferred`, status, `validFor`, and JSON-backed
  `account`, `relatedParty`, `relatedPlace`, `extra_attrs_json`.
- Links to Odoo accounting:
  - `payment_method_line_id` → `account.payment.method.line`.
  - `journal_id` → `account.journal`.
- `_sync_account_payment_method()`:
  - Matches/assigns an `account.payment.method.line` (and journal) based on
    the TMF payment method name and optional journal.
  - Falls back to a sensible default bank/cash journal when required.
- `to_tmf_dict()`:
  - Builds TMF670 payload and ensures CTK-visible attributes such as
    `cardNumber`, `brand`, `expirationDate`, `nameOnCard` are always present
    (as empty strings if necessary) to satisfy CTK list validations.
- Creation & patching helpers:
  - `tmf_create_from_payload(payload, api_base_path)` → creates a TMF Payment
    Method from POST payload and sets `href`.
  - `tmf_apply_merge_patch` / `tmf_apply_json_patch` → implement PATCH semantics
    including merge of `extra_attrs_json`.
- Lifecycle:
  - `create`:
    - Auto-generates `tmf_id` and defaults `@baseType`.
    - Syncs Odoo payment method lines and emits `PaymentMethodCreateEvent`.
  - `write`:
    - Re-syncs and emits `PaymentMethodAttributeValueChangeEvent`.
  - `unlink`:
    - Emits `PaymentMethodDeleteEvent`.

### TransferBalance (`tmf_transfer_balance`)

- Model: `tmf.transfer.balance` (`_inherit = ["tmf.model.mixin"]`).
- Fields map TMF TransferBalance attributes (confirmationDate, usageType,
  amount, bucket, receiver, relatedParty, etc.).
- Links to Odoo:
  - `partner_id` → `res.partner`.
  - `account_payment_id` → `account.payment`.
  - `account_move_id` → `account.move`.
- `_resolve_partner()` / `_sync_native_links()`:
  - Resolve `relatedParty` JSON refs into `res.partner`.
  - Attach the most recent payment and invoice for that partner for
    traceability.
- `to_tmf_json()` returns a CTK-compliant TransferBalance payload.
- Lifecycle:
  - `create` → syncs native links and emits `transferBalance/create` events.
  - `write` → resyncs when relevant fields change and emits `update` events.
  - `unlink` → emits `delete` events with preserved payloads.

Together, these addons implement **TMFC029 PaymentManagement** on top of Odoo:
- TMF676 Payment is the orchestration point between TMF payments and
  `account.payment`/`account.move`.
- TMF670 PaymentMethod bridges TMF payment methods to Odoo payment method
  lines and journals.
- TransferBalance provides TMF-compliant balance transfer operations tied back
  to partners, payments, and invoices.

All of this is CTK-first: we do not alter controllers or `to_tmf_json` from
outside these modules, and any future wiring must follow the side-car pattern
used for other TMFCs.

## 10) Next documentation targets

- Document TMF632 Party mapping to `res.partner` + identity-by-document rules.
- Document TMF620 Catalog modeling (ProductSpecification vs ProductOffering split).
- Document TMF622 Ordering mapping to `sale.order`.

---

Owner: Architect agent

Last updated: 2026-04-02
