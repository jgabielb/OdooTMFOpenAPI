# TMF Open API Field Mapping Schema

**Version:** 1.0.0  
**Purpose:** Declarative YAML schema to replace hardcoded `to_tmf_json()` and `_sync_*` methods across 100+ OdooTMFOpenAPI modules.

---

## Overview

Each module's Python serialization/deserialization logic can be expressed as a YAML mapping file consumed by a shared `mapping_engine.py` runtime. This eliminates boilerplate, centralizes logic, and makes field relationships auditable without reading Python.

---

## File-Level Header

Every mapping file begins with a metadata block:

```yaml
spec_version: "1.0"          # Schema version (semver). Engine rejects incompatible versions.
odoo_version: "17.0"         # Odoo version compatibility. May be a list: ["16.0", "17.0"]
tmf_spec: "TMF620"           # TMF specification identifier
tmf_version: "5.0"           # TMF API version
description: "..."           # Human-readable description
```

---

## Top-Level Structure

```yaml
spec_version: "1.0"
odoo_version: "17.0"
tmf_spec: "TMF620"
tmf_version: "5.0"
description: "ProductOffering mapping for product.template"

mappings:
  - id: product_offering          # Unique mapping ID within this file
    odoo_model: product.template  # Odoo model technical name
    tmf_type: ProductOffering     # TMF @type value
    direction: bidirectional      # to_tmf | to_odoo | bidirectional
    fields:
      - ...                       # Field mapping entries (see below)
```

### `direction` values

| Value | Meaning |
|---|---|
| `to_tmf` | Only serialization (Odoo → TMF JSON) |
| `to_odoo` | Only sync (TMF JSON → Odoo) |
| `bidirectional` | Both directions are defined |

---

## Field Entry Types

Each entry in `fields` is a dict with a `type` discriminator.

### Type 1: `direct` — Simple field copy

Maps one Odoo field to one TMF key (or vice versa). The most common type.

```yaml
- type: direct
  odoo_field: name
  tmf_key: name
  direction: bidirectional      # optional; inherits mapping-level direction
```

**Optional modifiers:**

| Key | Effect |
|---|---|
| `transform` | Apply a named transform function (see Transforms section) |
| `default` | Fallback value if source field is falsy |
| `if_truthy` | Include in output only if the source value is truthy |
| `required` | Raise error on sync_to_odoo if key is missing in TMF payload |

```yaml
- type: direct
  odoo_field: lifecycle_status
  tmf_key: lifecycleStatus
  transform: capitalize
  if_truthy: true
```

---

### Type 2: `fallback` — Ordered fallback chain

Try each source in order; use the first truthy value. Supports cross-direction fallbacks.

```yaml
- type: fallback
  tmf_key: id
  sources:
    - odoo_field: tmf_id
    - odoo_field: id
      transform: str
  direction: to_tmf
```

```yaml
- type: fallback
  tmf_key: description
  sources:
    - odoo_field: description
    - odoo_field: name      # fallback to name if description is empty
  direction: to_tmf
```

---

### Type 3: `literal` — Hardcoded constant

Injects a fixed value into the TMF JSON. Common for `@type`, `@referredType`, `@schemaLocation`.

```yaml
- type: literal
  tmf_key: "@type"
  value: "ProductOffering"
  direction: to_tmf
```

---

### Type 4: `value_map` — State/enum translation

Maps discrete values between Odoo and TMF domains. Supports a `default` for unmapped values.

```yaml
- type: value_map
  odoo_field: state
  tmf_key: lifecycleStatus
  direction: bidirectional
  map:
    to_tmf:
      draft: acknowledged
      sent: acknowledged
      sale: inProgress
      done: completed
      cancel: cancelled
    to_odoo:
      acknowledged: draft
      inProgress: sale
      completed: done
      cancelled: cancel
  default:
    to_tmf: acknowledged
    to_odoo: draft
```

**Note:** `to_tmf` and `to_odoo` sub-maps are both optional. If only one direction is needed, use `direction: to_tmf` or `direction: to_odoo` and provide a flat `map` dict.

---

### Type 5: `many2one_ref` — Relational reference serialization

Serializes an Odoo Many2one field to a TMF reference object (id, href, @type, @referredType). On sync, resolves back to the Odoo record.

```yaml
- type: many2one_ref
  odoo_field: product_specification_id
  tmf_key: productSpecification
  direction: bidirectional
  ref_type: ProductSpecification         # TMF type name
  ref_odoo_model: product.specification  # Odoo model for reverse lookup
  id_field: tmf_id                       # Preferred ID field (falls back to str(id))
  name_field: name                       # Display name field
  href_template: "/tmf-api/productCatalogManagement/v5/productSpecification/{id}"
  if_truthy: true                        # Only include if the relation is set
```

**Serialized output:**
```json
{
  "id": "spec-001",
  "name": "My Spec",
  "href": "/tmf-api/productCatalogManagement/v5/productSpecification/spec-001",
  "@type": "ProductSpecificationRef",
  "@referredType": "ProductSpecification"
}
```

**Reverse (sync_to_odoo):** The engine will search `ref_odoo_model` by `tmf_id` then by integer ID then by name.

---

### Type 6: `related_party` — RelatedParty resolution

Handles the standard TMF `relatedParty` array (appears in 30+ modules). On `to_odoo`, resolves each party to an `res.partner` record.

```yaml
- type: related_party
  tmf_key: relatedParty
  odoo_field: partner_id           # Target Odoo field (Many2one to res.partner)
  direction: bidirectional
  role_filter: "Customer"          # Optional: only resolve parties with this role
  if_truthy: true
```

**Resolution order (to_odoo):**
1. `tmf_id` exact match
2. Integer ID → `Partner.browse(int(id))`
3. Name search `[("name", "=", name)]`

**Serialization (to_tmf):** Wraps the partner record as a `RelatedParty` object:
```json
{
  "id": "partner-42",
  "name": "Acme Corp",
  "@type": "RelatedParty",
  "role": "Customer"
}
```

---

### Type 7: `conditional_block` — Conditional field group

Includes a block of TMF keys only when a condition is met. Maps to `if/elif/else` Python logic.

```yaml
- type: conditional_block
  direction: to_tmf
  branches:
    - if_truthy_field: description
      emit:
        - type: direct
          odoo_field: description
          tmf_key: description
    - if_truthy_field: sale_order_id
      emit:
        - type: literal
          tmf_key: salesOpportunity
          value_from_field: sale_order_id.name
          wrap:
            "@type": "SalesOpportunityRef"
```

---

### Type 8: `nested_object` — Inline nested TMF object

Groups multiple field mappings into a nested JSON object in the TMF payload.

```yaml
- type: nested_object
  tmf_key: billingAccount
  if_truthy_field: account_id
  fields:
    - type: fallback
      tmf_key: id
      sources:
        - odoo_field: account_id.tmf_id
        - odoo_field: account_id.id
          transform: str
    - type: direct
      odoo_field: account_id.name
      tmf_key: name
    - type: literal
      tmf_key: "@type"
      value: "BillingAccountRef"
```

---

## Transforms

Named transforms applied to field values. Engine applies these after reading the source value.

| Name | Description | Example input → output |
|---|---|---|
| `str` | Cast to string | `42` → `"42"` |
| `int` | Cast to integer | `"42"` → `42` |
| `capitalize` | `str.capitalize()` | `"active"` → `"Active"` |
| `upper` | `str.upper()` | `"active"` → `"ACTIVE"` |
| `lower` | `str.lower()` | `"Active"` → `"active"` |
| `bool` | Cast to bool | `"true"` → `True` |
| `date_iso` | Format date as ISO8601 | `date(2024,1,1)` → `"2024-01-01"` |
| `datetime_iso` | Format datetime as ISO8601 | `datetime(...)` → `"2024-01-01T00:00:00Z"` |
| `strip` | Strip whitespace | `"  foo  "` → `"foo"` |

Custom transforms can be registered in the engine's `TRANSFORM_REGISTRY` dict.

---

## Conditions Reference

| Key | Applies to types | Meaning |
|---|---|---|
| `if_truthy` | direct, fallback, nested_object, many2one_ref, related_party | Skip field if source value is falsy |
| `if_truthy_field` | conditional_block branches | Evaluate a specific field for truthiness |
| `required` | direct | Raise `MappingError` on sync_to_odoo if key absent |

---

## Full Example: Minimal Bidirectional Mapping

```yaml
spec_version: "1.0"
odoo_version: "17.0"
tmf_spec: "TMF999"
tmf_version: "1.0"

mappings:
  - id: example_entity
    odoo_model: example.model
    tmf_type: ExampleEntity
    direction: bidirectional
    fields:
      - type: fallback
        tmf_key: id
        sources:
          - odoo_field: tmf_id
          - odoo_field: id
            transform: str
        direction: to_tmf

      - type: literal
        tmf_key: "@type"
        value: ExampleEntity
        direction: to_tmf

      - type: direct
        odoo_field: name
        tmf_key: name

      - type: value_map
        odoo_field: state
        tmf_key: status
        map:
          to_tmf:
            active: Active
            inactive: Inactive
          to_odoo:
            Active: active
            Inactive: inactive
        default:
          to_tmf: Active
          to_odoo: active
```

---

## Python Engine Consumption

The `mapping_engine.py` runtime consumes YAML files as follows:

```python
from tools.mapping_engine import MappingEngine

engine = MappingEngine("mappings/tmf620_product_catalog.yaml")

# Serialize Odoo record dict → TMF JSON
tmf_json = engine.to_tmf_json(record_dict, mapping_id="product_offering")

# Sync TMF payload → Odoo field values dict
odoo_vals = engine.sync_to_odoo(tmf_payload, mapping_id="product_offering")
# Then: odoo_record.write(odoo_vals)
```

The `record` passed to `to_tmf_json` is a plain Python `dict`. In Odoo context, serialize with:
```python
record_dict = {
    "id": self.id,
    "tmf_id": self.tmf_id,
    "name": self.name,
    # ... all fields referenced in the mapping
    "product_specification_id": {
        "id": self.product_specification_id.id,
        "tmf_id": self.product_specification_id.tmf_id,
        "name": self.product_specification_id.name,
    } if self.product_specification_id else None,
}
```

---

## Migration Guide

### Converting `to_tmf_json()` to YAML

**Before (Python):**
```python
def to_tmf_json(self):
    return {
        "id": self.tmf_id or str(self.id),
        "name": self.name,
        "lifecycleStatus": self.lifecycle_status.capitalize() if self.lifecycle_status else None,
        "@type": "ProductOffering",
    }
```

**After (YAML):**
```yaml
fields:
  - type: fallback
    tmf_key: id
    sources:
      - odoo_field: tmf_id
      - odoo_field: id
        transform: str
    direction: to_tmf

  - type: direct
    odoo_field: name
    tmf_key: name
    direction: to_tmf

  - type: direct
    odoo_field: lifecycle_status
    tmf_key: lifecycleStatus
    transform: capitalize
    if_truthy: true
    direction: to_tmf

  - type: literal
    tmf_key: "@type"
    value: ProductOffering
    direction: to_tmf
```

### Converting `_sync_*` to YAML

**Before (Python):**
```python
def _crm_vals(self):
    return {
        "name": self.name or "SalesLead",
        "description": self.description or False,
    }
```

**After (YAML):**
```yaml
fields:
  - type: fallback
    odoo_field: name
    tmf_key: name
    sources:
      - tmf_key: name
      - default: "SalesLead"
    direction: to_odoo

  - type: direct
    tmf_key: description
    odoo_field: description
    direction: to_odoo
```

---

## Edge Cases Requiring Python Fallback

The following patterns cannot be expressed purely in YAML and require custom Python hooks:

1. **Computed priority mapping** (`_tmf_priority_to_crm`): Multi-step numeric range translation. Use `value_map` for discrete values; custom `transform` for range logic.

2. **Derived status** (`_derive_tmf_status`): Status computed from multiple fields (e.g., `lead.stage_id + lead.probability`). Register a custom transform function.

3. **Dynamic href base URL**: `href` templates with runtime-configured base URLs. Use `href_template` with env-variable substitution (engine reads `TMF_BASE_URL` env var).

4. **One-to-many (O2M) array serialization**: e.g., `productCharacteristic` list from `attribute_value_ids`. Use `nested_object` for now; full O2M support is planned for schema v1.1.

5. **Conditional Many2many partner resolution**: When `relatedParty` maps to multiple partners with different roles to different Odoo fields simultaneously.

6. **Write-time create vs. update logic**: The engine produces `vals` dicts; callers decide `create()` vs `write()`. Complex upsert logic (search-or-create) stays in Python.

7. **Currency and UOM conversions**: Require runtime context (pricelist, currency) not available in a stateless YAML mapping.

---

## Versioning & Compatibility

- `spec_version` is checked against the engine version at load time. Minor version differences emit a warning; major version mismatches raise an error.
- `odoo_version` is informational only — the engine does not enforce it.
- Schema v1.x is additive; unknown keys are ignored for forward compatibility.

---

*Schema designed for OdooTMFOpenAPI — replaces 100+ modules' serialization boilerplate with a single runtime engine.*
