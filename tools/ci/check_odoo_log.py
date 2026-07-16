#!/usr/bin/env python3
"""CI gate: scan an Odoo logfile for errors that indicate a broken build.

Fails (exit 1) on lines containing ERROR/CRITICAL log levels, Python tracebacks,
or registry-load failures — unless the line matches an allowlist pattern below.
The allowlist starts empty; add specific known-noise regexes as they are triaged,
each with a comment saying why it is acceptable.

Usage: python tools/ci/check_odoo_log.py <logfile>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FAIL_PATTERNS = (
    re.compile(r" (ERROR|CRITICAL) "),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"Failed to (load|initialize) (the )?registry"),
    re.compile(r"Some modules are not loaded"),
)

# Known-noise lines that must NOT fail the build. Keep each entry justified.
ALLOWLIST: tuple[re.Pattern[str], ...] = (
    # (empty — extend as CI iterations surface acceptable noise)
)

MAX_REPORTED = 40


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_odoo_log.py <logfile>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"ERROR: logfile not found: {path}", file=sys.stderr)
        return 2

    offending: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if any(p.search(line) for p in FAIL_PATTERNS) and not any(
            a.search(line) for a in ALLOWLIST
        ):
            offending.append(line)

    if offending:
        print(f"FAIL: {len(offending)} offending line(s) in {path}:")
        for line in offending[:MAX_REPORTED]:
            print("  " + line[:300])
        if len(offending) > MAX_REPORTED:
            print(f"  ... and {len(offending) - MAX_REPORTED} more")
        return 1
    print(f"OK: no blocking errors in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
