"""Audit all TMF module controllers for HTTP verb coverage and hub notification."""
import os
import re
import sys

base = sys.argv[1] if len(sys.argv) > 1 else "."

results = []
for mod in sorted(os.listdir(base)):
    if not (mod.startswith("tmf_") or mod.startswith("tmfc")):
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

    has_get    = bool(re.search(r'methods=\[["\']GET', content))
    has_post   = bool(re.search(r'methods=\[["\']POST', content))
    has_patch  = bool(re.search(r'methods=\[["\']PATCH', content))
    has_delete = bool(re.search(r'methods=\[["\']DELETE', content))
    has_hub    = "_notify_subscribers" in content
    route_count = len(re.findall(r"@http\.route", content))
    crud = sum([has_get, has_post, has_patch, has_delete])
    results.append((mod, has_get, has_post, has_patch, has_delete, has_hub, crud, route_count))

print(f"{'Module':<55} {'GET':>3} {'POST':>4} {'PATCH':>5} {'DEL':>3} {'Hub':>3} {'CRUD':>4} {'Routes':>6}")
print("-" * 88)
for mod, g, p, pa, d, h, crud, rc in results:
    print(f"{mod:<55} {'Y' if g else '-':>3} {'Y' if p else '-':>4} {'Y' if pa else '-':>5} {'Y' if d else '-':>3} {'Y' if h else '-':>3} {crud:>4}/4 {rc:>6}")

print()
full_crud  = sum(1 for r in results if r[6] == 4)
has_hub_ct = sum(1 for r in results if r[4])
print(f"Total modules: {len(results)}")
print(f"Full CRUD (GET+POST+PATCH+DELETE): {full_crud}/{len(results)}")
print(f"Hub notifications (_notify_subscribers): {has_hub_ct}/{len(results)}")
