# UI Post-Generation Enhancer

## Purpose

This repository does not currently expose one obvious single generator/template implementation for all `generated_views.xml` files.

To make UI quality reproducible anyway, use the repo-owned post-generation enhancer:

- `tools/apply_ui_generator_defaults.py`

This script is the executable bridge between:
- raw generated XML
- the UI standards documented in:
  - `UI_DESIGN_STANDARD.md`
  - `UI_GENERATOR_DEFAULTS.md`

---

## What it does today

When run against `generated_views.xml`, it can automatically:

1. ensure `ir.actions.act_window` has `view_mode="list,form"`
2. add contextual `help` blocks when missing
3. create a basic `search` view when none exists
4. wire `search_view_id` into actions

The generated search views intentionally use **flat Odoo-19-safe structures**:
- direct `<field/>`
- direct `<filter/>`
- optional `<separator/>`

This avoids the validator issues encountered earlier with more complex search structures.

---

## What it does not yet do

It does **not** yet fully rewrite forms into notebook-based business-first layouts.

That remains a source-level design task and should be implemented either:
- in a future true generator/template layer, or
- via additional post-generation transforms once those transforms are stable enough

---

## Recommended usage

### Dry run

```powershell
python tools/apply_ui_generator_defaults.py .
```

### Apply in place

```powershell
python tools/apply_ui_generator_defaults.py . --write
```

### Apply to one module

```powershell
python tools/apply_ui_generator_defaults.py tmf_account --write
```

---

## Recommended pipeline position

Use this script **after** any automatic module/view generation step.

Suggested flow:

1. generate module/view XML
2. run `apply_ui_generator_defaults.py`
3. run Odoo validation / module upgrade
4. review any remaining business-specific layout refinements

---

## Architectural role

This script is the current practical default path for making generated modules start closer to the desired UX quality.

It is not the final ideal state.
The ideal long-term state is still:
- a true template/generator layer that emits this quality directly

But until that generator source is centralized or exposed, this enhancer is the repo-owned enforcement step. 🏛️
