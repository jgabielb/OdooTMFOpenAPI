# Odoo 19 Compatibility Audit - OdooTMFOpenAPI

## Executive summary

### Overall recommendation
Proceed with YAML migration **selectively**:
- **Proceed now** for low-risk, serialization-centric modules that already have clear `to_tmf_json` structures and no hard Odoo 19 blockers.
- **Fix the red modules first** before attempting YAML extraction for bidirectional or sync-heavy modules.

In practical terms: start YAML work on the green/yellow modules with clear serializers, but **do not** treat the red modules as safe migration candidates until their manifest and model coupling issues are corrected.

### Highest-risk patterns across the codebase
1. **Missing manifest dependencies for fields/models assumed at runtime**
   - `tmf_customer/models/tmf_customer.py` accesses `res.partner.tmf_id`, but `tmf_customer/__manifest__.py` does not depend on `tmf_party`.
   - `tmf_service_order/models/main_model.py`, `tmf_resource_order/models/main_model.py`, and `tmf_appointment/models/main_model.py` also search or serialize `res.partner.tmf_id` without declaring `tmf_party` in their manifests.
   - `tmf_trouble_ticket/models/main_model.py` syncs to `helpdesk.ticket` / `helpdesk.team`, but `tmf_trouble_ticket/__manifest__.py` does not depend on `helpdesk`.
   - `tmf_product_ordering/controllers/ordering_controller.py` references `tmf.quote`, but `tmf_product_ordering/__manifest__.py` does not depend on `tmf_quote_management`.
2. **Large `type="http"` controllers with manual JSON parsing and public write routes**
   - Common pattern: `auth="public"`, `csrf=False`, `json.loads(request.httprequest.data or b"{}")`.
   - This is not inherently broken in Odoo 19, but it is brittle and spreads request parsing / error handling across many endpoints.
3. **Cross-module sync logic embedded directly in model `create`/`write` hooks**
   - Example: `tmf_service_order` -> `project.task`, `tmf_resource_order` -> `project.task` + `stock.picking`, `tmf_appointment` -> `calendar.event`, `tmf_trouble_ticket` -> `helpdesk.ticket`.
   - This increases upgrade risk because a field or dependency shift in Odoo 19 affects business logic immediately.
4. **Overloaded single files for model families and controller families**
   - `tmf_resource_order/models/main_model.py`, `tmf_geographic_address/models/main_model.py`, `tmf_product_catalog/controllers/catalog_controller.py`, `tmf_trouble_ticket/controllers/main_controller.py`.
   - Odoo 19 itself does not forbid this, but it makes migration audits and incremental fixes harder.

### Safest patterns already aligned with Odoo 19
1. **Explicit `_name` + list `_inherit` on native model extensions**
   - Good examples:
     - `tmf_party/models/res_partner.py`
     - `tmf_product_catalog/models/product_template.py`
     - `tmf_product_ordering/models/sale_order.py`
     - `tmf_billing_management/models/account_move.py`
   - This is the correct pattern to avoid warning-prone inheritance when extending native models with a mixin in modern Odoo.
2. **Use of `@api.model_create_multi` in many models**
   - Present in `tmf_sales`, `tmf_customer`, `tmf_quote_management`, `tmf_billing_management`, `tmf_service_order`, `tmf_resource_order`, `tmf_appointment`, `tmf_trouble_ticket`.
   - This is a good Odoo 19-safe pattern.
3. **View XML avoids classic deprecated `attrs` / `states` usage**
   - Across the audited modules, the views are mostly simple `<form>` / `<list>` definitions and inherited views.
   - I did **not** find `attrs=` or `states=` in the scoped modules.
4. **`list,form` action modes already used instead of legacy `tree,form`**
   - Example: `tmf_product_ordering/views/generated_views.xml`, `tmf_customer/views/tmf_customer_views.xml`, `tmf_billing_management/views/billing_views.xml`.
   - This is aligned with newer Odoo view terminology.

### YAML migration timing
- **Green/yellow serializer-focused modules:** migration can proceed now.
- **Red modules:** fix manifest dependencies and hard runtime coupling first.
- **Sync-heavy modules:** extract serialization first; defer reverse-sync YAML until the module boundaries are cleaned up.

---

## Module-by-module audit

### 1) `tmf_sales`
**Status:** yellow

**Why**
- Core model code is reasonably modern: `tmf_sales/models/main_model.py` uses `_name = "tmf.sales.lead"`, `_inherit = ["tmf.model.mixin"]`, and `@api.model_create_multi`.
- Native bridge extension is acceptable for Odoo 19: `tmf_sales/models/crm_lead_bridge.py` uses `_inherit = "crm.lead"` without old API decorators.
- Main risk is not inheritance; it is the large controller surface in `tmf_sales/controllers/main_controller.py`.

**Specific Odoo 19 risks**
- `tmf_sales/controllers/main_controller.py` uses many `type="http"` public routes with manual body parsing via `request.httprequest.data` and `json.loads(...)`.
- The module depends on multiple TMF modules (`tmf_quote_management`, `tmf_agreement`, `tmf_party_role`, `tmf_process_flow`), so upgrade failures in those modules can cascade into this one.
- `tmf_sales/models/main_model.py` searches several external TMF references (`tmf.quote`, `tmf.agreement`, `tmf.party.role`, `tmf.process.flow`); any renamed or unavailable model will break sync paths quickly.

**Concrete remediation actions**
- Keep the model layer as-is; the inheritance pattern is acceptable.
- Consolidate request parsing into a helper shared by all HTTP endpoints.
- Add defensive `env.registry.get(...)` checks or tighter module dependency guarantees for cross-module resolution paths.
- Add targeted migration tests around `crm.lead` bridge create/write behavior in Odoo 19.

---

### 2) `tmf_product_catalog`
**Status:** yellow

**Why**
- `tmf_product_catalog/models/product_template.py` uses the Odoo 19-friendly extension pattern:
  - `_name = 'product.template'`
  - `_inherit = ['product.template', 'tmf.model.mixin']`
- Views are simple and compatible-looking; no `attrs` / `states` issues found.
- The main risk is controller size and branching complexity.

**Specific Odoo 19 risks**
- `tmf_product_catalog/controllers/catalog_controller.py` is very large and multiplexes many resources and HTTP methods in one file; this is maintainability risk during migration.
- Controllers rely on `request.httprequest.method` branching and repeated manual `json.loads(request.httprequest.data)`.
- `tmf_product_catalog/models/product_template.py` overrides `create` with `@api.model` instead of `@api.model_create_multi`; this is still valid, but less future-proof and less efficient for batch creates.

**Concrete remediation actions**
- Keep the explicit `_name + _inherit` pattern; it is the correct Odoo 19 choice.
- Split `catalog_controller.py` by TMF resource (`productOffering`, `productSpecification`, `productOfferingPrice`, hub/listener endpoints).
- Convert single-record `create` overrides to `@api.model_create_multi` where practical.
- Add a small compatibility test that installs the module on Odoo 19 and exercises create/write/unlink on `product.template`.

---

### 3) `tmf_product_ordering`
**Status:** yellow

**Why**
- The native model extension pattern is explicitly Odoo 19-aware:
  - `tmf_product_ordering/models/sale_order.py` sets `_name = 'sale.order'` and `_inherit = ['sale.order', 'tmf.model.mixin']`
  - same for `sale.order.line`
- Views already use `<list>` and `view_mode` `list,form`.
- The main blocker is dependency coupling, not view or inheritance syntax.

**Specific Odoo 19 risks**
- `tmf_product_ordering/controllers/ordering_controller.py` references `tmf.quote` and writes `sale_order_id` back to quote records, but `tmf_product_ordering/__manifest__.py` does **not** depend on `tmf_quote_management`.
- This can become an install/upgrade/runtime failure if the controller path is reached without that module loaded.
- Controller logic manually provisions fallback records (`product.template`, partner lookups) under public routes, which is risky operationally even if not Odoo 19-specific.

**Concrete remediation actions**
- Add `tmf_quote_management` to `tmf_product_ordering/__manifest__.py` if quote linkage is required.
- If quote linkage is optional, guard it with `if request.env.registry.get('tmf.quote')` before using it.
- Keep the current `_name + _inherit` pattern; that part is aligned with Odoo 19.
- Add tests for `sale.order` extension and quote-linked order creation on Odoo 19.

---

### 4) `tmf_customer`
**Status:** red

**Why**
- The serializer/deserializer is simple, but the module has a hard dependency mismatch.
- `tmf_customer/models/tmf_customer.py` directly uses `partner_id.tmf_id` and searches `res.partner` by `tmf_id`.
- `tmf_customer/__manifest__.py` depends on `tmf_base` and `tmf_product_catalog`, but **not** `tmf_party`, which is where `res.partner` is extended with TMF fields.

**Specific Odoo 19 risks**
- Hard runtime assumption on `res.partner.tmf_id`:
  - `tmf_customer/models/tmf_customer.py` serializes `self.partner_id.tmf_id`
  - `map_tmf_to_odoo()` searches `[('tmf_id', '=', str(party_id))]`
- On a clean install or partial upgrade path, Odoo 19 will not magically provide that field; this is a manifest integrity problem, not just a warning.
- Controller still uses public `type="http"` routes and raw body parsing.

**Concrete remediation actions**
- Add `tmf_party` to `tmf_customer/__manifest__.py`.
- Optionally guard partner TMF field usage with `if 'tmf_id' in self.env['res.partner']._fields` where graceful degradation is acceptable.
- After dependency correction, this module becomes a good YAML candidate because `to_tmf_json()` and `map_tmf_to_odoo()` are both compact and clear.

---

### 5) `tmf_party`
**Status:** green

**Why**
- This is one of the cleaner Odoo 19-aligned modules in the scope.
- `tmf_party/models/res_partner.py` uses the correct extension form for native models:
  - `_name = "res.partner"`
  - `_inherit = ['res.partner', 'tmf.model.mixin']`
- `@api.model_create_multi` is used.
- Views are simple and do not use deprecated XML constructs.

**Specific Odoo 19 risks**
- `tmf_party/controllers/main_controller.py` still uses public `type="http"` endpoints with manual content-type parsing and public writes.
- There is a catch-all delete route (`@http.route(f'{TMF_BASE}/<path:subpath>', ... methods=['DELETE'])`) that could become a maintenance hazard, though not an Odoo 19 syntax issue.

**Concrete remediation actions**
- Keep the inheritance pattern unchanged.
- Refactor controller payload parsing into helpers and reduce catch-all route usage.
- Add regression tests around `res.partner` create/write/unlink notifications under Odoo 19.

---

### 6) `tmf_quote_management`
**Status:** yellow

**Why**
- No direct Odoo 19 inheritance anti-patterns found.
- Manifest dependencies are relatively complete for the referenced business models.
- Risk is concentrated in controller and JSON blob handling, not views.

**Specific Odoo 19 risks**
- `tmf_quote_management/models/tmf_quote.py` stores many structured TMF fragments in `fields.Text` and repeatedly `json.loads(...)` them inside `to_tmf_json()`.
- `tmf_quote_management/controllers/quote_controller.py` uses explicit `request.env.cr.rollback()` inside controller code paths; this is legal, but brittle and harder to reason about during upgrades.
- `tmf_quote_management/models/tmf_quote.py` uses `partner_id.tmf_id`, but this module correctly depends on `tmf_party`.

**Concrete remediation actions**
- Prefer a shared JSON field helper or validated accessors for all stored JSON fragments.
- Move transaction management away from controllers where possible.
- Add tests covering quote serialization with empty/invalid JSON text fields on Odoo 19.

---

### 7) `tmf_billing_management`
**Status:** green

**Why**
- `tmf_billing_management/models/account_move.py` uses the modern native extension pattern:
  - `_name = 'account.move'`
  - `_inherit = ['account.move', 'tmf.model.mixin']`
- Manifest dependencies are appropriate: `account`, `tmf_party`, `tmf_product_catalog`.
- Views are simple and use modern `list,form` action modes.

**Specific Odoo 19 risks**
- Minimal Odoo 19-specific risk found.
- Main caution is functional, not compatibility: `account_move.py` builds a simplified document URL (`/web/content/account.move/{id}/action_invoice_sent`) that may not match the desired download UX in newer versions.
- `billing_controller.py` still follows the manual HTTP parsing pattern.

**Concrete remediation actions**
- Keep the current extension strategy.
- Add a small test around invoice serialization (`invoice_date`, `invoice_date_due`, `payment_state`, `currency_id`) on Odoo 19.
- Treat URL generation as an application concern, not a compatibility blocker.

---

### 8) `tmf_geographic_address`
**Status:** yellow

**Why**
- Model code is generally modern and uses `@api.model_create_multi`.
- View XML is simple and Odoo 19-friendly.
- Main concerns are controller behavior and the amount of logic packed into one model file.

**Specific Odoo 19 risks**
- `tmf_geographic_address/controllers/main_controller.py` performs a write-side action from a GET path: `tmf.geographic.address.seed().ensure_seed_data()`.
- `tmf_geographic_address/models/main_model.py` defines multiple models plus a seed helper in one file; not a syntax problem, but migration noise is high.
- Serialization is host URL-sensitive (`to_tmf_json(host_url=...)`), which increases the risk of inconsistent behavior between worker / request contexts.

**Concrete remediation actions**
- Remove automatic seed writes from GET endpoints; move seeding to demo data or an explicit admin action.
- Split `main_model.py` into separate files for address, sub-address, validation, and seeding logic.
- Keep current view XML; no Odoo 19 XML blockers identified.

---

### 9) `tmf_service_order`
**Status:** red

**Why**
- Serializer and project sync are straightforward, but the manifest is incomplete for the fields it assumes.
- `tmf_service_order/models/main_model.py` searches `res.partner` by `tmf_id` in `_resolve_partner_from_related_party()`.
- `tmf_service_order/__manifest__.py` depends on `tmf_base`, `tmf_product_catalog`, and `project`, but **not** `tmf_party`.

**Specific Odoo 19 risks**
- Hard runtime dependency on `res.partner.tmf_id` without declaring `tmf_party`.
- Sync logic writes directly to `project.task` inside model hooks, so installation or upgrade order matters more than it should.
- Public HTTP routes continue the same manual parsing pattern.

**Concrete remediation actions**
- Add `tmf_party` to `tmf_service_order/__manifest__.py`.
- Guard partner TMF field lookups if soft dependency behavior is desired.
- After dependency cleanup, keep YAML extraction focused on serialization first; defer project sync extraction.

---

### 10) `tmf_resource_order`
**Status:** red

**Why**
- This is one of the more complex modules in the scope.
- It combines a large model family, validation rules, project sync, stock picking sync, and nested TMF item structures.
- It also has the same undeclared `tmf_party` coupling issue.

**Specific Odoo 19 risks**
- `tmf_resource_order/models/main_model.py` searches `res.partner` by `tmf_id` in `_resolve_partner_from_related_party()`, but `tmf_resource_order/__manifest__.py` does not depend on `tmf_party`.
- The module syncs to both `project.task` and `stock.picking` in `_sync_fulfillment_records()`, so any model or field drift in Odoo 19 has more blast radius here than in simpler modules.
- The module uses many nested helper models and related fields inside one file, increasing migration complexity.

**Concrete remediation actions**
- Add `tmf_party` to `tmf_resource_order/__manifest__.py`.
- Split the file into smaller model units before deeper migration work.
- Keep validation logic, but isolate stock/project sync behind helper services or adapters.
- Defer YAML sync extraction until after Odoo 19 installation and end-to-end tests are green.

---

### 11) `tmf_appointment`
**Status:** red

**Why**
- The core serializer is understandable and calendar sync is simple, but there is an undeclared dependency on TMF partner fields.
- `tmf_appointment/models/main_model.py` conditionally checks for `tmf_id` in `_resolve_partner()`, but `to_tmf_json()` later directly accesses `self.partner_id.tmf_id`.
- `tmf_appointment/__manifest__.py` depends on `calendar` and `contacts`, but **not** `tmf_party`.

**Specific Odoo 19 risks**
- Inconsistent handling of the partner TMF field:
  - safe check in `_resolve_partner()`
  - unsafe direct access in `to_tmf_json()`
- That means installs or upgrades without `tmf_party` can still fail at serialization time.
- Calendar sync itself is relatively Odoo 19-safe, but it is tightly coupled to record lifecycle hooks.

**Concrete remediation actions**
- Add `tmf_party` to `tmf_appointment/__manifest__.py`.
- Make `to_tmf_json()` use `getattr(self.partner_id, 'tmf_id', False)` or an `_fields` check before direct access.
- Keep calendar sync out of initial YAML extraction; start with serializer extraction only.

---

### 12) `tmf_trouble_ticket`
**Status:** red

**Why**
- This module has the strongest set of compatibility and maintainability concerns in the audited scope.
- `tmf_trouble_ticket/models/main_model.py` syncs to `helpdesk.ticket` / `helpdesk.team`, but `tmf_trouble_ticket/__manifest__.py` does not declare `helpdesk`.
- The model file defines **two `create()` methods** on `TroubleTicket`; the second one overwrites the first, so the initial sequence-setting logic is dead code.

**Specific Odoo 19 risks**
- Missing manifest dependency for `helpdesk` while sync code assumes those models exist.
- Duplicate `create()` definitions in the same class (`tmf_trouble_ticket/models/main_model.py`) make behavior fragile and easy to misread during migration.
- Controller file multiplexes both trouble tickets and ticket specifications with method branching on `request.httprequest.method`.

**Concrete remediation actions**
- Add `helpdesk` to `tmf_trouble_ticket/__manifest__.py`, or fully guard all helpdesk sync paths and make them optional.
- Merge the two `create()` methods into one coherent implementation.
- Separate ticket and specification controllers.
- Do not start YAML sync extraction here until the manifest and lifecycle-hook issues are fixed.

---

## Cross-cutting view XML assessment

### Safe patterns found
- `view_mode` uses `list,form` in the audited modules.
- Views are simple form/list/search definitions.
- No `attrs=` or `states=` usage found in the scoped modules.

### Potential watch items
- Many generated views are minimal and assume all referenced fields exist exactly as defined today.
- For native model inherited forms, verify each injected field still exists after all module loads on Odoo 19 (especially TMF-added fields on `sale.order`, `account.move`, `res.partner`).

---

## Recommended fix order before broader Odoo 19 rollout
1. Fix manifest dependency integrity:
   - `tmf_customer` -> add `tmf_party`
   - `tmf_service_order` -> add `tmf_party`
   - `tmf_resource_order` -> add `tmf_party`
   - `tmf_appointment` -> add `tmf_party`
   - `tmf_trouble_ticket` -> add `helpdesk`
   - `tmf_product_ordering` -> add `tmf_quote_management` or guard quote usage
2. Remove structural dead code / ambiguity:
   - merge duplicate `create()` methods in `tmf_trouble_ticket`
3. Reduce controller migration surface:
   - centralize request parsing / response helpers
   - split oversized controller files
4. Then continue YAML migration starting with serializer-first modules.
