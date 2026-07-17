#!/usr/bin/env python3
"""ODA Component conformance declaration generator.

Joins TMFC component requirements (extracted from the TM Forum ODA component
spec YAMLs) with the SID coverage produced by tools/gen_sid_coverage.py and the
addons present in this repository, and emits:

  docs/ODA_CONFORMANCE.md      per-component conformance declarations
  docs/oda_conformance.json    machine-readable mirror (feeds Canvas profiles)

Modes:
  --extract --specs-dir <dir>  (local-only, needs PyYAML) parse TMFC*.yaml specs
                               and rewrite mappings/tmfc_requirements.json
  (default)                    stdlib-only join; safe to run in CI
  --check                      regenerate in memory and diff against disk (CI gate)

Curation happens in mappings/tmfc_conformance_overrides.json only — never edit
the outputs.

Examples:
  python tools/gen_oda_conformance.py --extract --specs-dir "C:\\...\\ODAComponentDocumentation"
  python tools/gen_oda_conformance.py --strict
  python tools/gen_oda_conformance.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATUS_LABELS = {
    "declarable": "✅",
    "partial": "⚠️",
    "not_declarable": "❌",
    "waived": "➖",
}
SID_OK_STATUSES = {"covered", "partial", "na"}
VERSION_PART_RE = re.compile(r"^v\d")
BE_SUFFIX_RE = re.compile(r"[_ ]BE$")
ABE_SUFFIX_RE = re.compile(r"[_ ]ABE$")

# v25.0 spec domains that were renamed/merged in GB922 v25.5
DOMAIN_HINTS = {
    "Market & Sales Domain": ["Market Domain", "Sales Domain"],
    "Party Domain": ["Shared Domain"],
}


# ---------------------------------------------------------------------------
# Extract mode: TMFC spec YAMLs -> mappings/tmfc_requirements.json
# ---------------------------------------------------------------------------


def _flatten_resources(raw: object) -> dict[str, list[str]]:
    """resources: [{serviceSpecification: [GET, ...]}, ...] -> {name: verbs}."""
    out: dict[str, list[str]] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                for name, verbs in item.items():
                    out[str(name)] = [str(v) for v in (verbs or [])]
            elif isinstance(item, str):
                out[item] = []
    return out


def _extract_apis(raw: object) -> list[dict]:
    apis = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        apis.append(
            {
                "id": str(entry.get("id", "")),
                "name": str(entry.get("name", "")),
                "required": bool(entry.get("required", False)),
                "resources": _flatten_resources(entry.get("resources")),
            }
        )
    return sorted(apis, key=lambda a: (a["id"], a["name"]))


def extract_requirements(specs_dir: Path, out_path: Path) -> int:
    import yaml  # local-only dependency; CI never runs --extract

    components: dict[str, dict] = {}
    for path in sorted(specs_dir.glob("*/TMFC*/TMFC*.yaml")):
        match = re.match(r"(TMFC\d+)", path.stem)
        if not match:
            continue
        cid = match.group(1)
        doc = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
        spec = (doc or {}).get("spec", {}) or {}
        meta = spec.get("componentMetadata", {}) or {}
        core = spec.get("coreFunction", {}) or {}
        components[cid] = {
            "name": str(meta.get("name", "")),
            "functional_block": str(meta.get("functionalBlock", "")),
            "spec_version": str(meta.get("version", "")),
            "status": str(meta.get("status", "")),
            "exposed_apis": _extract_apis(core.get("exposedAPIs")),
            "dependent_apis": _extract_apis(core.get("dependentAPIs")),
            "sids": [str(s) for s in (meta.get("SIDs") or [])],
            "etoms": [str(e) for e in (meta.get("eTOMs") or [])],
            "source_file": path.name,
        }

    if not components:
        print(f"ERROR: no TMFC*.yaml specs found under {specs_dir}", file=sys.stderr)
        return 2

    payload = {
        "_comment": (
            "Extracted from the TM Forum ODA component spec YAMLs by "
            "tools/gen_oda_conformance.py --extract. Factual requirement data "
            "(API ids, SID ABE references); regenerate when specs update."
        ),
        "schema_version": 1,
        "specs_source": "TM Forum ODA component specifications (local ODAComponentDocumentation folder)",
        "components": {cid: components[cid] for cid in sorted(components)},
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"extracted {len(components)} components -> {out_path}")
    return 0


# ---------------------------------------------------------------------------
# SID reference resolution against docs/sid_abe_coverage.json
# ---------------------------------------------------------------------------


@dataclass
class SidIndex:
    abes_by_name: dict[str, list[dict]] = field(default_factory=dict)
    entity_by_key: dict[tuple[str, str], dict] = field(default_factory=dict)
    entities_by_name: dict[str, list[tuple[dict, dict]]] = field(default_factory=dict)


def build_sid_index(coverage: dict) -> SidIndex:
    idx = SidIndex()
    for domain in coverage.get("domains", []):
        for abe in domain.get("abes", []):
            abe = dict(abe, domain=domain["name"])
            idx.abes_by_name.setdefault(abe["name"], []).append(abe)
            for ent in abe.get("entities", []):
                idx.entity_by_key[(abe["name"], ent["name"])] = ent
                idx.entities_by_name.setdefault(ent["name"], []).append((abe, ent))
    return idx


def _norm_part(part: str) -> str:
    return re.sub(r"\s+", " ", part.replace("_", " ")).strip()


@dataclass
class SidResolution:
    raw: str
    status: str = "unresolved"   # covered|partial|missing|na|waived|unresolved
    abe: str = ""
    entity: str = ""
    detail: str = ""


def resolve_sid_ref(raw: str, idx: SidIndex, overrides: dict) -> SidResolution:
    res = SidResolution(raw=raw)

    remap = (overrides.get("sid_ref_remaps") or {}).get(raw)
    if remap:
        if remap.get("status") == "waived":
            res.status, res.detail = "waived", remap.get("reason", "waived")
            return res
        abe_name, ent_name = remap.get("abe", ""), remap.get("entity", "")
        abes = idx.abes_by_name.get(abe_name, [])
        if abes:
            res.abe = abe_name
            if ent_name and (abes[0]["name"], ent_name) in idx.entity_by_key:
                ent = idx.entity_by_key[(abes[0]["name"], ent_name)]
                res.entity = ent_name
                res.status = _entity_status(ent)
            else:
                res.status = abes[0]["status"]
            res.detail = "curated remap"
            return res
        res.detail = f"remap target ABE '{abe_name}' not found"
        return res

    parts = [p for p in raw.split("|") if p.strip()]
    if parts and VERSION_PART_RE.match(parts[-1].strip()):
        parts = parts[:-1]
    if len(parts) < 2:
        res.detail = "unparseable reference"
        return res

    domain_hint = _norm_part(parts[0])
    hint_domains = DOMAIN_HINTS.get(domain_hint, [domain_hint])
    path = [_norm_part(p) for p in parts[1:]]

    entity_name = ""
    if path and BE_SUFFIX_RE.search(path[-1]):
        entity_name = BE_SUFFIX_RE.sub("", path[-1]).replace(" ", "")
        path = path[:-1]

    # resolve deepest ABE path part first
    abe_hit: dict | None = None
    for part in reversed(path):
        name = part if part.endswith(" ABE") else ABE_SUFFIX_RE.sub("", part) + " ABE"
        candidates = idx.abes_by_name.get(name, [])
        if len(candidates) > 1:
            preferred = [c for c in candidates if c["domain"] in hint_domains]
            candidates = preferred or candidates[:1]
        if candidates:
            abe_hit = candidates[0]
            break

    if entity_name:
        ent = idx.entity_by_key.get((abe_hit["name"], entity_name)) if abe_hit else None
        if ent is None:
            global_hits = idx.entities_by_name.get(entity_name, [])
            if len(global_hits) == 1:
                abe_hit, ent = global_hits[0]
        if ent is not None and abe_hit is not None:
            res.abe, res.entity = abe_hit["name"], entity_name
            res.status = _entity_status(ent)
            return res
        if abe_hit is not None:
            # BE not in GB922 v25.5 under that name (spec refs are v25.0);
            # fall back to the ABE-level status with a note
            res.abe = abe_hit["name"]
            res.status = abe_hit["status"]
            res.detail = f"entity '{entity_name}' not in GB922 v25.5; ABE-level status used"
            return res
        res.detail = f"entity '{entity_name}' not found"
        return res

    if abe_hit is not None:
        res.abe = abe_hit["name"]
        res.status = abe_hit["status"]
        return res
    res.detail = "no ABE path part found in GB922 v25.5"
    return res


def _entity_status(ent: dict) -> str:
    return {"mapped": "covered", "proxy": "partial"}.get(ent.get("status", ""), "missing")


# ---------------------------------------------------------------------------
# Join mode
# ---------------------------------------------------------------------------


def parse_readme_api_modules(readme_path: Path) -> dict[str, str]:
    """README tables map '| TMFxxx | ... | `module_name` |' -> {TMFxxx: module}."""
    mapping: dict[str, str] = {}
    if not readme_path.is_file():
        return mapping
    row_re = re.compile(r"^\|\s*(TMF\d+\w*)\s*\|.*`([a-z0-9_]+)`\s*\|\s*$")
    for line in readme_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = row_re.match(line.strip())
        if m:
            mapping.setdefault(m.group(1), m.group(2))
    return mapping


@dataclass
class ApiCheck:
    api_id: str
    required: bool
    module: str = ""
    present: bool = False


@dataclass
class ComponentResult:
    cid: str
    data: dict
    verdict: str = "not_declarable"
    wiring_present: bool = False
    exposed: list[ApiCheck] = field(default_factory=list)
    dependent: list[ApiCheck] = field(default_factory=list)
    sid_results: list[SidResolution] = field(default_factory=list)
    waiver: str = ""
    problems: list[str] = field(default_factory=list)


def evaluate_components(
    requirements: dict,
    idx: SidIndex,
    overrides: dict,
    api_modules: dict[str, str],
    repo_root: Path,
) -> list[ComponentResult]:
    api_overrides = overrides.get("api_module_overrides") or {}
    waivers = overrides.get("component_waivers") or {}
    results: list[ComponentResult] = []

    known_cids = set(requirements["components"])
    for cid, reason in sorted(waivers.items()):
        if cid not in known_cids:
            results.append(
                ComponentResult(
                    cid=cid,
                    data={"name": (overrides.get("component_names") or {}).get(cid, cid),
                          "functional_block": "", "spec_version": "",
                          "exposed_apis": [], "dependent_apis": [], "sids": []},
                    verdict="waived",
                    waiver=reason,
                    wiring_present=(repo_root / f"{cid.lower()}_wiring" / "__manifest__.py").is_file(),
                )
            )

    for cid in sorted(requirements["components"]):
        data = requirements["components"][cid]
        result = ComponentResult(cid=cid, data=data)
        result.wiring_present = (
            repo_root / f"{cid.lower()}_wiring" / "__manifest__.py"
        ).is_file()
        if cid in waivers:
            result.verdict, result.waiver = "waived", waivers[cid]
            results.append(result)
            continue

        for section, target in (("exposed_apis", result.exposed),
                                ("dependent_apis", result.dependent)):
            for api in data.get(section, []):
                check = ApiCheck(api_id=api["id"], required=api.get("required", False))
                check.module = api_overrides.get(api["id"]) or api_modules.get(api["id"], "")
                check.present = bool(
                    check.module and (repo_root / check.module / "__manifest__.py").is_file()
                )
                target.append(check)

        for raw in data.get("sids", []):
            res = resolve_sid_ref(raw, idx, overrides)
            if res.status == "unresolved":
                result.problems.append(f"unresolved SID ref: {raw} ({res.detail})")
            result.sid_results.append(res)

        mandatory = [c for c in result.exposed if c.required] or result.exposed
        apis_ok = all(c.present for c in mandatory) if mandatory else True
        apis_any = any(c.present for c in result.exposed)
        sids_ok = all(
            r.status in SID_OK_STATUSES or r.status == "waived"
            for r in result.sid_results
        )
        sids_any = any(r.status in SID_OK_STATUSES for r in result.sid_results)

        if result.wiring_present and apis_ok and sids_ok:
            result.verdict = "declarable"
        elif result.wiring_present and (apis_any or sids_any or not result.sid_results):
            result.verdict = "partial"
        else:
            result.verdict = "not_declarable"
        results.append(result)

    return sorted(results, key=lambda r: r.cid)


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    # newline-normalized so hashes match across Windows (CRLF) and CI (LF) checkouts
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def render_markdown(
    results: list[ComponentResult], input_hashes: dict[str, str], sid_version: str
) -> str:
    lines: list[str] = []
    lines.append("# ODA Component Conformance Declarations")
    lines.append("")
    lines.append(
        "> Generated by `tools/gen_oda_conformance.py` - do not edit by hand. "
        "Curate `mappings/tmfc_conformance_overrides.json` (and regenerate "
        "`mappings/tmfc_requirements.json` from the spec YAMLs) instead."
    )
    lines.append("")
    lines.append(f"Inputs (SHA-256): " + ", ".join(
        f"`{name}` `{digest[:12]}`" for name, digest in sorted(input_hashes.items())
    ))
    lines.append(f"SID reference model: GB922 v{sid_version} (spec SIDs cite v25.0; names resolved best-effort).")
    lines.append("")
    lines.append("Verdict rules:")
    lines.append(
        f"- {STATUS_LABELS['declarable']} declarable - wiring addon present, all "
        "mandatory exposed APIs implemented by a repo addon, and every SID ABE "
        "requirement covered or partially covered in the SID matrix."
    )
    lines.append(f"- {STATUS_LABELS['partial']} partial - wiring present but some APIs or SID ABEs are not yet satisfied.")
    lines.append(f"- {STATUS_LABELS['not_declarable']} not declarable - wiring or core requirements absent.")
    lines.append(f"- {STATUS_LABELS['waived']} waived - curated waiver (reason shown).")
    lines.append("")

    counts = {"declarable": 0, "partial": 0, "not_declarable": 0, "waived": 0}
    for r in results:
        counts[r.verdict] += 1
    lines.append(
        f"Summary: {counts['declarable']} declarable / {counts['partial']} partial / "
        f"{counts['not_declarable']} not declarable / {counts['waived']} waived "
        f"({len(results)} components)."
    )
    lines.append("")
    lines.append("| TMFC | Name | Block | Wiring | Exposed APIs | SID ABEs | Verdict |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        exposed_ok = sum(1 for c in r.exposed if c.present)
        sid_ok = sum(1 for s in r.sid_results if s.status in SID_OK_STATUSES or s.status == "waived")
        lines.append(
            f"| {r.cid} | {r.data.get('name', '')} | {r.data.get('functional_block', '')} "
            f"| {'✅' if r.wiring_present else '❌'} "
            f"| {exposed_ok}/{len(r.exposed)} | {sid_ok}/{len(r.sid_results)} "
            f"| {STATUS_LABELS[r.verdict]} |"
        )
    lines.append("")

    for r in results:
        lines.append(f"## {r.cid} — {r.data.get('name', '')}")
        lines.append("")
        if r.waiver:
            lines.append(f"{STATUS_LABELS['waived']} **Waived**: {r.waiver}")
            lines.append("")
            continue
        lines.append(
            f"Spec v{r.data.get('spec_version', '?')} · block {r.data.get('functional_block', '?')} · "
            f"wiring `{r.cid.lower()}_wiring` {'✅' if r.wiring_present else '❌'} · "
            f"verdict {STATUS_LABELS[r.verdict]} {r.verdict.replace('_', ' ')}"
        )
        lines.append("")
        if r.exposed:
            lines.append("| Exposed API | Mandatory | Module | Present |")
            lines.append("|---|---|---|---|")
            for c in r.exposed:
                lines.append(
                    f"| {c.api_id} | {'yes' if c.required else 'no'} "
                    f"| {('`' + c.module + '`') if c.module else '-'} "
                    f"| {'✅' if c.present else '❌'} |"
                )
            lines.append("")
        if r.dependent:
            present = sum(1 for c in r.dependent if c.present)
            deps = ", ".join(
                f"{c.api_id}{'✅' if c.present else '·'}" for c in r.dependent
            )
            lines.append(f"Dependent APIs ({present}/{len(r.dependent)} locally implemented): {deps}")
            lines.append("")
        if r.sid_results:
            lines.append("| SID requirement | Resolved to | Status |")
            lines.append("|---|---|---|")
            for s in r.sid_results:
                target = s.abe + (f" / {s.entity}" if s.entity else "")
                icon = {"covered": "✅", "partial": "⚠️", "na": "➖", "waived": "➖"}.get(s.status, "❌")
                note = f" ({s.detail})" if s.detail else ""
                lines.append(f"| `{s.raw}` | {target or '-'}{note} | {icon} {s.status} |")
            lines.append("")
        else:
            lines.append("No SID requirements declared in the component spec.")
            lines.append("")
    return "\n".join(lines) + "\n"


def render_json(
    results: list[ComponentResult], input_hashes: dict[str, str], sid_version: str
) -> str:
    counts = {"declarable": 0, "partial": 0, "not_declarable": 0, "waived": 0}
    for r in results:
        counts[r.verdict] += 1
    payload = {
        "generator": "tools/gen_oda_conformance.py",
        "inputs": dict(sorted(input_hashes.items())),
        "sid_version": sid_version,
        "summary": counts,
        "components": {
            r.cid: {
                "name": r.data.get("name", ""),
                "functional_block": r.data.get("functional_block", ""),
                "spec_version": r.data.get("spec_version", ""),
                "verdict": r.verdict,
                "waiver": r.waiver or None,
                "wiring_present": r.wiring_present,
                "exposed_apis": [
                    {"id": c.api_id, "mandatory": c.required, "module": c.module or None,
                     "present": c.present}
                    for c in r.exposed
                ],
                "dependent_apis": [
                    {"id": c.api_id, "module": c.module or None, "present": c.present}
                    for c in r.dependent
                ],
                "sid_requirements": [
                    {"ref": s.raw, "abe": s.abe or None, "entity": s.entity or None,
                     "status": s.status, "detail": s.detail or None}
                    for s in r.sid_results
                ],
                "problems": r.problems,
            }
            for r in results
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate ODA component conformance declarations.")
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--requirements", default="", help="default: <repo>/mappings/tmfc_requirements.json")
    parser.add_argument("--coverage", default="", help="default: <repo>/docs/sid_abe_coverage.json")
    parser.add_argument("--overrides", default="", help="default: <repo>/mappings/tmfc_conformance_overrides.json")
    parser.add_argument("--out-dir", default="", help="default: <repo>/docs")
    parser.add_argument("--extract", action="store_true", help="rebuild tmfc_requirements.json from spec YAMLs")
    parser.add_argument("--specs-dir", default="", help="ODAComponentDocumentation folder (with --extract)")
    parser.add_argument("--strict", action="store_true", help="unresolved SID refs become errors")
    parser.add_argument("--check", action="store_true", help="verify outputs on disk are up to date (CI gate)")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except AttributeError:
        pass
    args = parse_args()
    repo_root = Path(args.repo_root)
    req_path = Path(args.requirements) if args.requirements else repo_root / "mappings" / "tmfc_requirements.json"
    cov_path = Path(args.coverage) if args.coverage else repo_root / "docs" / "sid_abe_coverage.json"
    ovr_path = Path(args.overrides) if args.overrides else repo_root / "mappings" / "tmfc_conformance_overrides.json"
    out_dir = Path(args.out_dir) if args.out_dir else repo_root / "docs"

    if args.extract:
        if not args.specs_dir:
            print("ERROR: --extract requires --specs-dir", file=sys.stderr)
            return 2
        return extract_requirements(Path(args.specs_dir), req_path)

    for path in (req_path, cov_path):
        if not path.is_file():
            print(f"ERROR: required input missing: {path}", file=sys.stderr)
            return 2
    requirements = json.loads(req_path.read_text(encoding="utf-8"))
    coverage = json.loads(cov_path.read_text(encoding="utf-8"))
    overrides = (
        json.loads(ovr_path.read_text(encoding="utf-8")) if ovr_path.is_file() else {}
    )

    idx = build_sid_index(coverage)
    api_modules = parse_readme_api_modules(repo_root / "README.md")
    results = evaluate_components(requirements, idx, overrides, api_modules, repo_root)

    problems = [p for r in results for p in r.problems]
    for problem in problems:
        print(f"{'ERROR' if args.strict else 'WARNING'}: {problem}", file=sys.stderr)
    if args.strict and problems:
        return 2

    input_hashes = {
        req_path.name: _sha256(req_path),
        cov_path.name: _sha256(cov_path),
    }
    if ovr_path.is_file():
        input_hashes[ovr_path.name] = _sha256(ovr_path)
    sid_version = coverage.get("sid_source", {}).get("version", "?")

    md = render_markdown(results, input_hashes, sid_version)
    js = render_json(results, input_hashes, sid_version)
    md_path = out_dir / "ODA_CONFORMANCE.md"
    js_path = out_dir / "oda_conformance.json"

    if args.check:
        stale = []
        for path, content in ((md_path, md), (js_path, js)):
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(str(path))
        if stale:
            print("FAIL: conformance outputs out of date, regenerate with "
                  "tools/gen_oda_conformance.py:", file=sys.stderr)
            for s in stale:
                print("  " + s, file=sys.stderr)
            return 1
        print("OK: conformance outputs are in sync")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")
    js_path.write_text(js, encoding="utf-8")
    counts = {"declarable": 0, "partial": 0, "not_declarable": 0, "waived": 0}
    for r in results:
        counts[r.verdict] += 1
    print(
        f"components={len(results)} "
        + " ".join(f"{k}={v}" for k, v in counts.items())
        + f" sid_ref_problems={len(problems)}"
    )
    print(f"wrote {md_path} and {js_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
