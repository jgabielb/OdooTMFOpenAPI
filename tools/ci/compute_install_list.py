#!/usr/bin/env python3
"""Print the CI module install list: core Odoo apps + every tmf_*/tmfc* addon.

Usage: python tools/ci/compute_install_list.py [repo_root]
Output: a single comma-separated list suitable for `odoo -i`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ODOO_APPS = [
    "base",
    "contacts",
    "calendar",
    "crm",
    "sale_management",
    "stock",
    "account",
    "purchase",
    "project",
]

EXCLUDE = {
    # depends on Enterprise-only 'helpdesk'; not installable on Community images
    "tmf_service_level_objective",
}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    mods = sorted(
        p.name
        for p in root.iterdir()
        if (p / "__manifest__.py").is_file()
        and (p.name.startswith("tmf_") or p.name.startswith("tmfc"))
        and p.name not in EXCLUDE
    )
    if not mods:
        print("ERROR: no tmf addons found under " + str(root), file=sys.stderr)
        return 1
    print(",".join(ODOO_APPS + mods))
    return 0


if __name__ == "__main__":
    sys.exit(main())
