"""Report modules missing PATCH, DELETE, or Hub notification."""
import os
import re
import sys

base = sys.argv[1] if len(sys.argv) > 1 else "."

incomplete = []
for mod in sorted(os.listdir(base)):
    if not mod.startswith("tmf_"):
        continue
    ctrl_dir = os.path.join(base, mod, "controllers")
    if not os.path.isdir(ctrl_dir):
        continue
    content = ""
    for f in os.listdir(ctrl_dir):
        if f.endswith(".py") and f != "__init__.py":
            try:
                with open(os.path.join(ctrl_dir, f), encoding="utf-8", errors="ignore") as fh:
                    content += fh.read()
            except Exception:
                pass
    if not content:
        continue
    has_get    = bool(re.search(r'methods=\[["\']+GET', content))
    has_post   = bool(re.search(r'methods=\[["\']+POST', content))
    has_patch  = bool(re.search(r'methods=\[["\']+PATCH', content))
    has_delete = bool(re.search(r'methods=\[["\']+DELETE', content))
    has_hub    = "_notify_subscribers" in content

    missing = []
    if not has_post:   missing.append("POST")
    if not has_patch:  missing.append("PATCH")
    if not has_delete: missing.append("DELETE")
    if not has_hub:    missing.append("Hub")
    if missing:
        incomplete.append((mod, has_get, has_post, has_patch, has_delete, has_hub, missing))

print(f"{'Module':<55} {'Missing'}")
print("-" * 80)
for row in incomplete:
    mod, g, p, pa, d, h, miss = row
    print(f"{mod:<55} {', '.join(miss)}")

print()
print(f"Total modules with gaps: {len(incomplete)}")

# Categorize
no_hub = [r[0] for r in incomplete if "Hub" not in r[6] or True]
only_hub_missing = [r[0] for r in incomplete if r[6] == ["Hub"]]
crud_gaps = [r for r in incomplete if any(x in r[6] for x in ["POST","PATCH","DELETE"])]
print(f"Hub missing: {sum(1 for r in incomplete if 'Hub' in r[6])}")
print(f"PATCH missing: {sum(1 for r in incomplete if 'PATCH' in r[6])}")
print(f"DELETE missing: {sum(1 for r in incomplete if 'DELETE' in r[6])}")
print(f"POST missing: {sum(1 for r in incomplete if 'POST' in r[6])}")
