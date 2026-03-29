# Next YAML Conversion Candidates

## Selection criteria used
I ranked candidates using four signals from `tools/mapping_training_data.json`, `tools/mapping_registry_index.json`, and the code audit:
1. **Low transform complexity** - fewer field pairs and fewer nested/computed transforms.
2. **Low Odoo 19 risk** - no red install/runtime blockers, or only trivial blockers.
3. **Clear `to_tmf_json` structure** - serializer concentrated in one model and easy to map.
4. **Minimal reverse-sync ambiguity** - little or no hidden sync behavior outside the serializer.

Already-converted modules with YAML in the registry were excluded:
- `tmf_sales`
- `tmf_product_catalog`

---

## Ranked top 5

### 1) `tmf_party`
- **Why it is a good candidate**
  - `mapping_training_data.json` has only **11** mappings for this module.
  - `mapping_registry_index.json` shows **no sync methods**.
  - `tmf_party/models/res_partner.py` contains a compact serializer with clear branch logic for `Individual` vs `Organization`.
  - Odoo 19 posture is good because the native model extension uses explicit `_name = "res.partner"` with `_inherit = ['res.partner', 'tmf.model.mixin']`.
- **Expected YAML complexity:** low
- **Recommended conversion scope:** **serialization only**
- **Why not both serialization + sync?**
  - The outbound serialization is clean, but inbound controller logic still contains resource-specific branching (`individual` vs `organization`) that is better left in Python for now.

### 2) `tmf_billing_management`
- **Why it is a good candidate**
  - `mapping_training_data.json` has **15** mappings total, still relatively small.
  - Registry shows **no sync methods**.
  - Both serializers are straightforward:
    - `tmf_billing_management/models/billing_account.py`
    - `tmf_billing_management/models/account_move.py`
  - The Odoo 19 extension pattern for `account.move` is already correct.
- **Expected YAML complexity:** low
- **Recommended conversion scope:** **serialization only**
- **Why not both serialization + sync?**
  - The POST controller behavior still creates related parties/accounts procedurally; serializer extraction is safe, reverse mapping is still application-specific.

### 3) `tmf_customer`
- **Why it is a good candidate**
  - `mapping_training_data.json` has only **10** mappings.
  - Serializer and deserializer are both compact in `tmf_customer/models/tmf_customer.py`.
  - `to_tmf_json()` and `map_tmf_to_odoo()` are explicit and easy to express in YAML.
- **Expected YAML complexity:** low
- **Recommended conversion scope:** **both serialization + sync**, **but only after the manifest fix**
- **Important condition**
  - This is a good YAML candidate **after** adding `tmf_party` to `tmf_customer/__manifest__.py`.
  - Until that fix lands, it remains an Odoo 19 red module and should not be migrated first.

### 4) `tmf_product_ordering`
- **Why it is a good candidate**
  - `mapping_training_data.json` has only **10** mappings.
  - Registry shows **no sync methods**.
  - `tmf_product_ordering/models/sale_order.py` has a single concentrated `to_tmf_json()` for `sale.order` and a small serializer for `tmf.cancel.product.order`.
  - The `_name + _inherit` pattern is already Odoo 19-aware for both `sale.order` and `sale.order.line`.
- **Expected YAML complexity:** low to medium
- **Recommended conversion scope:** **serialization only**
- **Important condition**
  - Add `tmf_quote_management` to the manifest or guard quote usage first, because the controller references `tmf.quote`.

### 5) `tmf_quote_management`
- **Why it is a good candidate**
  - Registry shows **no sync methods**.
  - All outbound mapping is concentrated in `tmf_quote_management/models/tmf_quote.py`.
  - Most complexity is not structural mapping ambiguity; it is repeated `json.loads(...)` of stored JSON fragments, which YAML can still represent clearly.
  - Dependency posture is better than several other candidates because `tmf_quote_management/__manifest__.py` already declares the major linked modules.
- **Expected YAML complexity:** medium
- **Recommended conversion scope:** **serialization only**
- **Why not both serialization + sync?**
  - Inbound quote creation/update logic still mixes controller concerns, partner resolution, item creation, and transaction handling.

---

## Near-miss candidates

### `tmf_appointment`
- Good serializer shape and only **19** mappings.
- Not selected in the top 5 because it has a **red Odoo 19 dependency issue**: `tmf_appointment/models/main_model.py` accesses `partner_id.tmf_id`, but the manifest does not depend on `tmf_party`.
- Best future scope: serialization only, after manifest cleanup.

### `tmf_geographic_address`
- Mapping count is manageable (**20**), and serializer structure is mostly linear.
- Not selected because the module still mixes address, sub-address, validation, and seed logic in one place; there is also GET-triggered seed behavior in the controller.
- Best future scope: serialization only.

### `tmf_service_order`
- Serializer is clear, but registry already shows a sync method (`_sync_project_task`).
- Not selected because it is both **sync-coupled** and **red** on manifest integrity (`res.partner.tmf_id` without `tmf_party` dependency).

### `tmf_resource_order`
- Too much coupled behavior for an early YAML extraction: nested items, validation rules, project sync, stock sync, and undeclared TMF partner dependency.

### `tmf_trouble_ticket`
- Blocked by missing `helpdesk` dependency and duplicate `create()` definitions in the model class.

---

## Recommended execution order
1. `tmf_party`
2. `tmf_billing_management`
3. `tmf_customer` *(after adding `tmf_party` dependency)*
4. `tmf_product_ordering` *(after fixing quote dependency integrity)*
5. `tmf_quote_management`

---

## Practical migration strategy
- **Wave 1:** `tmf_party`, `tmf_billing_management`
- **Wave 2:** `tmf_customer`, `tmf_product_ordering` after manifest fixes
- **Wave 3:** `tmf_quote_management`
- Keep `tmf_service_order`, `tmf_resource_order`, `tmf_appointment`, and `tmf_trouble_ticket` out of early YAML waves until the Odoo 19 blockers are resolved.
