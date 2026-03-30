# Generation Workflow

## Purpose

This repository does not currently expose one obvious single in-repo generator implementation for all `generated_views.xml` files.

To make UI quality reproducible anyway, the default workflow should now be:

1. run your generation step
2. run the repo UI post-generation enhancer
3. validate in Odoo

---

## Default wrapper

Use:

- `tools/regenerate_and_enhance_ui.ps1`

This wrapper standardizes the workflow even if the upstream generator command varies by context.

---

## Recommended flow

### 1. If you already know the generator command

Example:

```powershell
powershell -ExecutionPolicy Bypass -File tools/regenerate_and_enhance_ui.ps1 \
  -Target . \
  -GeneratorCommand "<your real generation command here>" \
  -Validate \
  -Modules "tmf_service_inventory,tmf_product_offering_qualification"
```

### 2. If generation has already happened

Example:

```powershell
powershell -ExecutionPolicy Bypass -File tools/regenerate_and_enhance_ui.ps1 \
  -Target . \
  -Validate \
  -Modules "tmf_service_inventory,tmf_product_offering_qualification"
```

---

## What the wrapper guarantees

- runs `apply_ui_generator_defaults.py --write`
- optionally runs Odoo module validation
- gives the repo a repeatable standard path even without a centralized generator source

---

## Relationship to the UI docs

This workflow operationalizes:

- `tools/UI_DESIGN_STANDARD.md`
- `tools/UI_GENERATOR_DEFAULTS.md`
- `tools/UI_POSTGEN_ENHANCER.md`

---

## Current architectural truth

### Today
- generation source is not clearly centralized in this repo
- generated outputs are present
- UI quality is improved through post-generation enforcement + source cleanup

### Target state
Eventually, the true generator/template layer should emit this quality directly.
Until then, this wrapper is the repo-owned default workflow.

---

## Next engineering recommendation

Once the real generation entry point is identified or centralized, update this wrapper so `-GeneratorCommand` no longer needs to be supplied manually.
That is the next maturity step. 🏛️
