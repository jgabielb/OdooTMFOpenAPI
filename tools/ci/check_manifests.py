#!/usr/bin/env python3
"""Lint gate: validate every addon __manifest__.py in the repo.

Checks (errors fail the build):
  - manifest parses via ast.literal_eval and is a dict
  - required keys present: name, depends
  - every file listed in 'data'/'demo' exists on disk
  - every 'depends' entry is a repo addon or a known core/community module

Enterprise-only dependencies produce a WARNING (the addon must also be excluded
from the CI install list — see compute_install_list.py).

Usage: python tools/ci/check_manifests.py [repo_root]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Odoo core/community modules the tmf addons legitimately depend on.
CORE_ALLOWLIST = {
    "base", "web", "mail", "contacts", "calendar", "crm", "sale",
    "sale_management", "stock", "account", "purchase", "project",
    "product", "payment", "portal", "utm", "resource", "uom",
    "analytic", "digest", "http_routing", "bus", "rpc",
}

ENTERPRISE_MODULES = {"helpdesk", "planning", "documents", "sign", "industry_fsm",
                      "account_accountant", "quality", "marketing_automation"}

REQUIRED_KEYS = ("name", "depends")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    manifests = sorted(root.glob("*/__manifest__.py"))
    repo_addons = {p.parent.name for p in manifests}
    errors: list[str] = []
    warnings: list[str] = []

    for path in manifests:
        addon = path.parent.name
        try:
            data = ast.literal_eval(path.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError) as exc:
            errors.append(f"{addon}: manifest does not parse ({exc})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{addon}: manifest is not a dict")
            continue
        for key in REQUIRED_KEYS:
            if key not in data:
                errors.append(f"{addon}: missing required key '{key}'")
        for section in ("data", "demo"):
            for rel in data.get(section, []) or []:
                if not (path.parent / rel).is_file():
                    errors.append(f"{addon}: {section} file missing: {rel}")
        for dep in data.get("depends", []) or []:
            if dep in repo_addons or dep in CORE_ALLOWLIST:
                continue
            if dep in ENTERPRISE_MODULES:
                warnings.append(
                    f"{addon}: depends on Enterprise-only '{dep}' "
                    "(must stay excluded from the CI install list)"
                )
            else:
                errors.append(f"{addon}: unknown dependency '{dep}'")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"checked {len(manifests)} manifests: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
