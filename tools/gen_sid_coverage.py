#!/usr/bin/env python3
"""
SID ABE -> Odoo model coverage matrix generator.

Joins the TM Forum GB922 SID model (Excel, "All Domains" sheet) against the
tmf_* / tmfc*_wiring Odoo addons in this repository and emits:

  docs/SID_ABE_COVERAGE_MATRIX.md    human-readable coverage matrix
  docs/sid_abe_coverage.json         entity-level detail (feeds ODA conformance)
  docs/sid_abe_coverage.csv          flat per-entity export
  docs/sid_abe_coverage.todo.json    review queue (ambiguous/unmatched stubs)

Curation happens in mappings/sid_abe_map.json only - never edit the outputs.

Examples:
  python tools/gen_sid_coverage.py
  python tools/gen_sid_coverage.py --dump-sid
  python tools/gen_sid_coverage.py --strict-overrides --fail-on-unmapped
"""

from __future__ import annotations

import argparse
import ast
import csv
import difflib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl


DEFAULT_EXCEL = (
    r"C:\Users\Joao Gabriel\OneDrive\work_area\DOCUMENTATION"
    r"\gb922-standards-addenda-for-information-framework-suite-v25-5"
    r"\information-framework-sid-excel-format-v25-5-gb922"
    r"\GB922_Information_Framework_SID_Excel_v25.5.xlsx"
)
SID_SHEET = "All Domains"
SID_VERSION = "25.5"
EXPECTED_COUNTS = {"domains": 10, "abes": 347, "entities": 1755}
EXPECTED_TMF_MODELS = 220  # matchable tmf.* / tmfNNN.* models (infra/mixins/hubs excluded)

PATTERNS_DOMAIN = "Patterns Domain"

STATUS_FULL_THRESHOLD = 0.75

# tmf.* plus API-numbered variants (tmf640.*, tmf654.*, ...); tmfc\d+.* is wiring infra
TMF_NAME_RE = re.compile(r"^tmf(\d+)?\.")
INFRA_MODELS = {
    "tmf.model.mixin",
    "tmf.api.key",
    "tmf.ui.normalizer",
}
# Mixins and event-plumbing (hubs/monitors/listeners) are not SID entities.
INFRA_NAME_PATTERNS = (
    re.compile(r"\.mixin$"),
    re.compile(r"^tmfc\d+\."),
    re.compile(r"\.hub(\.subscription)?$"),
    re.compile(r"\.monitor$"),
)

STATUS_LABELS = {
    "covered": "✅",
    "partial": "⚠️",
    "missing": "❌",
    "na": "➖",
}

MAPPED_TIERS = {"curated", "high", "medium"}
MAX_MODELS_IN_CELL = 4


# ---------------------------------------------------------------------------
# SID workbook parsing
# ---------------------------------------------------------------------------


@dataclass
class SidEntity:
    domain: str
    abe: str
    name: str
    attr_count: int = 0
    required_count: int = 0
    doc_excerpt: str = ""


@dataclass
class SidAbe:
    domain: str
    name: str        # short display name, e.g. "Customer ABE"
    qualified: str   # raw workbook value, e.g. "Customer Domain.Customer ABE"
    parent: str
    entities: list[SidEntity] = field(default_factory=list)


@dataclass
class SidModel:
    domains: list[str] = field(default_factory=list)
    abes: list[SidAbe] = field(default_factory=list)

    def abe_lookup(self) -> dict[str, list[SidAbe]]:
        by_name: dict[str, list[SidAbe]] = {}
        for abe in self.abes:
            by_name.setdefault(abe.name, []).append(abe)
            by_name.setdefault(abe.qualified, []).append(abe)
        return by_name

    def entities(self) -> list[SidEntity]:
        return [e for abe in self.abes for e in abe.entities]


def _excerpt(value: object, limit: int = 200) -> str:
    if not value:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit]


def load_sid_workbook(excel_path: Path) -> SidModel:
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb[SID_SHEET]
    sid = SidModel()
    current_domain = ""
    current_abe: SidAbe | None = None
    current_entity: SidEntity | None = None

    for row in ws.iter_rows(min_row=2, max_col=6, values_only=True):
        abe_col, be_col, attr_col, _origin, stereotype, doc = (
            (list(row) + [None] * 6)[:6]
        )
        abe_col = str(abe_col).strip() if abe_col else ""
        be_col = str(be_col).strip() if be_col else ""
        attr_col = str(attr_col).strip() if attr_col else ""

        if attr_col:
            if current_entity is not None:
                current_entity.attr_count += 1
                if stereotype and "required" in str(stereotype).lower():
                    current_entity.required_count += 1
            continue

        if be_col:
            if current_abe is None:
                # entity appearing before any ABE: attach to a synthetic bucket
                current_abe = SidAbe(
                    domain=current_domain,
                    name="(domain root)",
                    qualified=f"{current_domain}.(domain root)",
                    parent=current_domain,
                )
                sid.abes.append(current_abe)
            current_entity = SidEntity(
                domain=current_domain,
                abe=current_abe.name,
                name=be_col,
                doc_excerpt=_excerpt(doc),
            )
            current_abe.entities.append(current_entity)
            continue

        if abe_col:
            if abe_col.startswith("Business Entity."):
                current_domain = abe_col.split(".", 1)[1].strip()
                sid.domains.append(current_domain)
                current_abe = None
                current_entity = None
            else:
                if "." in abe_col:
                    parent, short = abe_col.rsplit(".", 1)
                else:
                    parent, short = current_domain, abe_col
                current_abe = SidAbe(
                    domain=current_domain,
                    name=short.strip(),
                    qualified=abe_col,
                    parent=parent.strip(),
                )
                sid.abes.append(current_abe)
                current_entity = None

    wb.close()

    counts = {
        "domains": len(sid.domains),
        "abes": len(sid.abes),
        "entities": len(sid.entities()),
    }
    for key, expected in EXPECTED_COUNTS.items():
        if counts[key] != expected:
            print(
                f"WARNING: SID {key} count {counts[key]} differs from expected "
                f"{expected} (workbook version drift?)",
                file=sys.stderr,
            )
    return sid


# ---------------------------------------------------------------------------
# Odoo addon scanning (AST-based)
# ---------------------------------------------------------------------------


@dataclass
class OdooModel:
    name: str
    addon: str
    file: str
    class_name: str
    description: str
    inherits: list[str] = field(default_factory=list)


def _const_strings(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        out: list[str] = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
        return out
    return []


def _is_infra(name: str) -> bool:
    if name in INFRA_MODELS:
        return True
    return any(p.search(name) for p in INFRA_NAME_PATTERNS)


def scan_odoo_models(repo_root: Path) -> tuple[list[OdooModel], dict[str, list[str]]]:
    """Return (tmf_models, native_extended {native model -> sorted addons})."""
    tmf_models: list[OdooModel] = []
    native_extended: dict[str, set[str]] = {}

    files: list[Path] = []
    for pattern in ("tmf_*/models/**/*.py", "tmfc*_wiring/models/**/*.py"):
        files.extend(repo_root.glob(pattern))

    for path in sorted(files):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            print(f"WARNING: skipping {path} ({exc})", file=sys.stderr)
            continue
        addon = path.relative_to(repo_root).parts[0]
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            name = description = ""
            inherits: list[str] = []
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                values = _const_strings(stmt.value)
                if "_name" in targets and values:
                    name = values[0]
                elif "_description" in targets and values:
                    description = values[0]
                elif "_inherit" in targets and values:
                    inherits = values

            if TMF_NAME_RE.match(name):
                if _is_infra(name):
                    continue
                tmf_models.append(
                    OdooModel(
                        name=name,
                        addon=addon,
                        file=str(path.relative_to(repo_root)).replace("\\", "/"),
                        class_name=node.name,
                        description=description,
                        inherits=inherits,
                    )
                )
            elif inherits:
                # extension of a native model, either anonymous (_inherit only)
                # or re-declared (_name = 'sale.order' + _inherit = 'sale.order')
                for target in inherits:
                    if not target.startswith(("tmf", "mail.")):
                        native_extended.setdefault(target, set()).add(addon)

    if abs(len(tmf_models) - EXPECTED_TMF_MODELS) > 10:
        print(
            f"WARNING: scanned {len(tmf_models)} TMF models, expected about "
            f"{EXPECTED_TMF_MODELS}",
            file=sys.stderr,
        )
    return tmf_models, {k: sorted(v) for k, v in sorted(native_extended.items())}


# ---------------------------------------------------------------------------
# Curated overrides
# ---------------------------------------------------------------------------


@dataclass
class Overrides:
    entity: dict[tuple[str, str], dict] = field(default_factory=dict)
    abe: dict[str, dict] = field(default_factory=dict)
    api_hints: dict[str, list[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def load_overrides(
    path: Path,
    sid: SidModel,
    tmf_models: list[OdooModel],
    native_extended: dict[str, list[str]],
) -> Overrides:
    ov = Overrides()
    if not path.exists():
        print(f"WARNING: overrides file not found: {path}", file=sys.stderr)
        return ov
    data = json.loads(path.read_text(encoding="utf-8"))

    abe_lookup = sid.abe_lookup()
    entity_names: dict[str, list[SidEntity]] = {}
    for ent in sid.entities():
        entity_names.setdefault(ent.name, []).append(ent)
    known_models = {m.name for m in tmf_models}

    def check_models(models: list[str], key: str) -> None:
        for model in models:
            if model.startswith("external:"):
                continue
            if model in known_models or model in native_extended:
                continue
            ov.problems.append(
                f"{key}: odoo model '{model}' not found in scan "
                f"(neither tmf model nor TMF-extended native model)"
            )

    def resolve_abe(name: str, key: str) -> SidAbe | None:
        hits = abe_lookup.get(name, [])
        uniq = {a.qualified: a for a in hits}
        if len(uniq) == 1:
            return next(iter(uniq.values()))
        if not uniq:
            ov.problems.append(f"{key}: ABE '{name}' not found in workbook")
        else:
            ov.problems.append(
                f"{key}: ABE '{name}' is ambiguous; use qualified name "
                f"({', '.join(sorted(uniq))})"
            )
        return None

    for key, spec in data.get("entity_overrides", {}).items():
        if key.startswith("_"):
            continue
        if "/" in key:
            abe_name, be_name = key.split("/", 1)
            abe = resolve_abe(abe_name.strip(), key)
            if abe is None:
                continue
            match = [e for e in abe.entities if e.name == be_name.strip()]
            if not match:
                ov.problems.append(f"{key}: entity '{be_name}' not in '{abe.name}'")
                continue
            ent = match[0]
        else:
            hits = entity_names.get(key.strip(), [])
            if len(hits) != 1:
                ov.problems.append(
                    f"{key}: bare entity name is "
                    + ("not found" if not hits else "ambiguous; use '<ABE>/<Entity>'")
                )
                continue
            ent = hits[0]
        check_models(spec.get("odoo_models", []), key)
        ov.entity[(ent.abe, ent.name)] = spec

    for name, spec in data.get("abe_overrides", {}).items():
        if name.startswith("_"):
            continue
        abe = resolve_abe(name.strip(), f"abe_overrides:{name}")
        if abe is None:
            continue
        check_models(spec.get("odoo_models", []), f"abe_overrides:{name}")
        if spec.get("status") == "not_applicable" and not spec.get("reason"):
            ov.problems.append(f"abe_overrides:{name}: not_applicable needs a reason")
        ov.abe[abe.name] = spec

    for name, apis in data.get("abe_api_hints", {}).items():
        if name.startswith("_"):
            continue
        abe = resolve_abe(name.strip(), f"abe_api_hints:{name}")
        if abe is not None:
            ov.api_hints[abe.name] = list(apis)

    return ov


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def model_keys(model: OdooModel) -> tuple[str, str]:
    """(normalized _name key, normalized _description key)."""
    name = TMF_NAME_RE.sub("", model.name, count=1)
    desc = model.description
    if desc.lower().startswith("tmf "):
        desc = desc[4:]
    return norm(name), norm(desc)


def expand_variants(key: str) -> set[str]:
    """Token expansions applied symmetrically to entity and model keys."""
    out: set[str] = set()
    if "specification" in key:
        out.add(key.replace("specification", "spec"))
    elif "spec" in key:
        out.add(key.replace("spec", "specification"))
    if key.endswith("reference"):
        out.add(key[: -len("erence")])
    elif key.endswith("ref"):
        out.add(key + "erence")
    out.discard(key)
    return out


@dataclass
class MatchIndex:
    name_index: dict[str, list[OdooModel]] = field(default_factory=dict)
    desc_index: dict[str, list[OdooModel]] = field(default_factory=dict)
    variant_index: dict[str, list[OdooModel]] = field(default_factory=dict)


def build_match_index(tmf_models: list[OdooModel]) -> MatchIndex:
    idx = MatchIndex()
    for model in tmf_models:
        name_key, desc_key = model_keys(model)
        if name_key:
            idx.name_index.setdefault(name_key, []).append(model)
        if desc_key:
            idx.desc_index.setdefault(desc_key, []).append(model)
        for base in {name_key, desc_key} - {""}:
            for variant in expand_variants(base):
                idx.variant_index.setdefault(variant, []).append(model)
    return idx


@dataclass
class EntityMatch:
    entity: SidEntity
    tier: str = ""            # curated | high | medium | inherited | ""
    models: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)  # for ambiguous
    note: str = ""

    @property
    def status(self) -> str:
        if self.tier in MAPPED_TIERS:
            return "mapped"
        if self.candidates:
            return "ambiguous"
        if self.tier == "inherited":
            return "proxy"
        return "unmatched"


def _distinct(models: list[OdooModel]) -> dict[str, list[OdooModel]]:
    out: dict[str, list[OdooModel]] = {}
    for m in models:
        out.setdefault(m.name, []).append(m)
    return out


def match_entities(
    sid: SidModel,
    idx: MatchIndex,
    overrides: Overrides,
    native_extended: dict[str, list[str]],
) -> list[EntityMatch]:
    entity_norms = {norm(e.name) for e in sid.entities()}
    matches: list[EntityMatch] = []

    for abe in sid.abes:
        abe_ov = overrides.abe.get(abe.name, {})
        for ent in abe.entities:
            m = EntityMatch(entity=ent)
            spec = overrides.entity.get((abe.name, ent.name))
            if spec is not None:
                m.tier = "curated"
                m.models = list(spec.get("odoo_models", []))
                m.modules = list(spec.get("modules", []))
                m.note = spec.get("note", "")
                matches.append(m)
                continue

            key = norm(ent.name)
            found: dict[str, list[OdooModel]] = {}
            tier = ""
            for tier_name, lookup in (
                ("high", idx.name_index.get(key)),
                ("high", idx.desc_index.get(key)),
            ):
                if lookup:
                    found = _distinct(lookup)
                    tier = tier_name
                    break

            if not found:
                variant_keys = set(expand_variants(key))
                if key.endswith("characteristic"):
                    stripped = key[: -len("characteristic")]
                    if stripped not in entity_norms:
                        variant_keys.add(stripped)
                hits: list[OdooModel] = list(idx.variant_index.get(key, []))
                for vkey in sorted(variant_keys):
                    hits.extend(idx.name_index.get(vkey, []))
                    hits.extend(idx.desc_index.get(vkey, []))
                if hits:
                    found = _distinct(hits)
                    tier = "medium"

            if found:
                names = sorted(found)
                if len(names) == 1:
                    m.tier = tier
                    m.models = names
                    m.modules = sorted({mm.addon for mm in found[names[0]]})
                else:
                    m.candidates = names
            elif abe_ov.get("odoo_models"):
                proxies = [
                    x for x in abe_ov["odoo_models"] if x in native_extended
                ]
                if proxies:
                    m.tier = "inherited"
                    m.models = sorted(proxies)
                    m.note = "coverage by ABE-level native mapping"
            matches.append(m)
    return matches


# ---------------------------------------------------------------------------
# ABE status computation
# ---------------------------------------------------------------------------


@dataclass
class AbeRow:
    abe: SidAbe
    status: str = "missing"        # covered | partial | missing | na
    mapped: int = 0
    total: int = 0
    models: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    tmf_apis: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def ratio(self) -> float:
        return self.mapped / self.total if self.total else 0.0


def compute_abe_rows(
    sid: SidModel,
    matches: list[EntityMatch],
    overrides: Overrides,
    native_extended: dict[str, list[str]],
) -> list[AbeRow]:
    by_entity = {(m.entity.abe, m.entity.name): m for m in matches}
    rows: list[AbeRow] = []
    for abe in sid.abes:
        row = AbeRow(abe=abe, total=len(abe.entities))
        ov = overrides.abe.get(abe.name, {})
        models: set[str] = set(ov.get("odoo_models", []))
        modules: set[str] = set()
        notes: list[str] = []

        for ent in abe.entities:
            m = by_entity[(abe.name, ent.name)]
            if m.tier in MAPPED_TIERS:
                row.mapped += 1
                models.update(m.models)
                modules.update(m.modules)

        for model in ov.get("odoo_models", []):
            if model in native_extended:
                modules.update(native_extended[model])

        apis = list(dict.fromkeys(ov.get("tmf_apis", []) + overrides.api_hints.get(abe.name, [])))

        if ov.get("status") == "not_applicable":
            row.status = "na"
            notes.append(ov.get("reason", ""))
        elif ov.get("coverage") == "full":
            row.status = "covered"
        elif row.total == 0:
            # container/overview ABEs carry no direct entities; nothing to map
            row.status = "partial" if (ov.get("coverage") == "partial" or models) else "na"
            notes.append("no direct entities (container ABE)")
        elif row.ratio >= STATUS_FULL_THRESHOLD:
            row.status = "covered"
        elif row.mapped > 0:
            row.status = "partial"
        elif ov.get("coverage") == "partial" or any(
            x in native_extended for x in ov.get("odoo_models", [])
        ):
            row.status = "partial"
            notes.append("native-model proxy coverage")
        else:
            row.status = "missing"

        if ov.get("note"):
            notes.append(ov["note"])
        row.models = sorted(models)
        row.modules = sorted(modules)
        row.tmf_apis = apis
        row.notes = "; ".join(n for n in notes if n)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------


def _cell_list(items: list[str]) -> str:
    if not items:
        return "-"
    if len(items) > MAX_MODELS_IN_CELL:
        extra = len(items) - MAX_MODELS_IN_CELL
        items = items[:MAX_MODELS_IN_CELL] + [f"+{extra} more"]
    return ", ".join(f"`{i}`" if not i.startswith("+") else i for i in items)


def _domain_stats(rows: list[AbeRow], matches_by_abe: dict[str, list[EntityMatch]]) -> dict:
    stat = {"abes": len(rows), "covered": 0, "partial": 0, "missing": 0, "na": 0,
            "entities": 0, "mapped": 0}
    for row in rows:
        stat[row.status] += 1
        stat["entities"] += row.total
        stat["mapped"] += row.mapped
    return stat


def emit_markdown(
    sid: SidModel,
    abe_rows: list[AbeRow],
    matches: list[EntityMatch],
    out_path: Path,
) -> None:
    matches_by_abe: dict[str, list[EntityMatch]] = {}
    for m in matches:
        matches_by_abe.setdefault(m.entity.abe, []).append(m)
    rows_by_domain: dict[str, list[AbeRow]] = {}
    for row in abe_rows:
        rows_by_domain.setdefault(row.abe.domain, []).append(row)

    lines: list[str] = []
    lines.append("# SID ABE -> Odoo Coverage Matrix (GB922 v" + SID_VERSION + ")")
    lines.append("")
    lines.append(
        "> Generated by `tools/gen_sid_coverage.py` - do not edit by hand. "
        "Curate `mappings/sid_abe_map.json` instead and regenerate."
    )
    lines.append("")
    lines.append("Legend:")
    lines.append(
        f"- {STATUS_LABELS['covered']} Covered - at least "
        f"{int(STATUS_FULL_THRESHOLD * 100)}% of the ABE's entities map to Odoo "
        "models (or curated as fully covered)."
    )
    lines.append(f"- {STATUS_LABELS['partial']} Partial - some entities mapped, or native-model proxy coverage.")
    lines.append(f"- {STATUS_LABELS['missing']} Missing - no entity of the ABE is mapped yet.")
    lines.append(f"- {STATUS_LABELS['na']} N/A - curated as out of scope (excluded from totals).")
    lines.append("")
    lines.append(
        "Entity-level detail lives in `docs/sid_abe_coverage.json`; the review "
        "queue of unmatched/ambiguous entities is `docs/sid_abe_coverage.todo.json`."
    )
    lines.append("")

    # Headline
    lines.append("## Headline")
    lines.append("")
    lines.append("| Domain | ABEs | Covered | Partial | Missing | N/A | Entity coverage |")
    lines.append("|---|---|---|---|---|---|---|")
    total = {"abes": 0, "covered": 0, "partial": 0, "missing": 0, "na": 0,
             "entities": 0, "mapped": 0}
    for domain in sid.domains:
        rows = rows_by_domain.get(domain, [])
        stat = _domain_stats(rows, matches_by_abe)
        label = domain
        if domain == PATTERNS_DOMAIN:
            label += " (framework, excluded from TOTAL)"
        else:
            for key in total:
                total[key] += stat[key]
        pct = f"{stat['mapped']}/{stat['entities']}"
        lines.append(
            f"| {label} | {stat['abes']} | {stat['covered']} | {stat['partial']} "
            f"| {stat['missing']} | {stat['na']} | {pct} |"
        )
    pct = (
        f"{total['mapped']}/{total['entities']} "
        f"({100 * total['mapped'] // max(total['entities'], 1)}%)"
    )
    lines.append(
        f"| **TOTAL (business domains)** | {total['abes']} | {total['covered']} "
        f"| {total['partial']} | {total['missing']} | {total['na']} | {pct} |"
    )
    lines.append("")

    # Domain sections
    for domain in sid.domains:
        rows = rows_by_domain.get(domain, [])
        if not rows:
            continue
        if domain == PATTERNS_DOMAIN:
            lines.append(f"## Domain: {domain} (framework - summarized)")
            lines.append("")
            lines.append(
                "The Patterns domain holds abstract framework classes (RootEntity, "
                "Characteristic pattern, EntitySpecification pattern). This "
                "repository realizes them architecturally - `tmf.model.mixin` "
                "(`tmf_base`), JSON characteristic fields, and the generic "
                "`tmf.entity` models - rather than one Odoo model per class, so "
                "entities are not enumerated here. Full entity detail is available "
                "in the JSON export via `--include-patterns-entities`."
            )
            lines.append("")
            lines.append("| ABE | Entities | Status | Odoo models | Notes |")
            lines.append("|---|---|---|---|---|")
            for row in rows:
                lines.append(
                    f"| {row.abe.name} | {row.total} | {STATUS_LABELS[row.status]} "
                    f"| {_cell_list(row.models)} | {row.notes or '-'} |"
                )
            lines.append("")
            continue
        lines.append(f"## Domain: {domain}")
        lines.append("")
        lines.append("| ABE | Entities | Status | Odoo models | Modules | TMF APIs | Notes |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in rows:
            entities = f"{row.mapped}/{row.total}" if row.total else "0"
            apis = ", ".join(row.tmf_apis) if row.tmf_apis else "-"
            lines.append(
                f"| {row.abe.name} | {entities} | {STATUS_LABELS[row.status]} "
                f"| {_cell_list(row.models)} | {_cell_list(row.modules)} "
                f"| {apis} | {row.notes or '-'} |"
            )
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def emit_json(
    sid: SidModel,
    abe_rows: list[AbeRow],
    matches: list[EntityMatch],
    tmf_models: list[OdooModel],
    native_extended: dict[str, list[str]],
    stats: dict,
    out_path: Path,
    include_patterns_entities: bool,
) -> None:
    by_entity = {(m.entity.abe, m.entity.name): m for m in matches}
    rows_by_domain: dict[str, list[AbeRow]] = {}
    for row in abe_rows:
        rows_by_domain.setdefault(row.abe.domain, []).append(row)

    domains = []
    for domain in sid.domains:
        abes = []
        for row in rows_by_domain.get(domain, []):
            entities = []
            if domain != PATTERNS_DOMAIN or include_patterns_entities:
                for ent in row.abe.entities:
                    m = by_entity[(row.abe.name, ent.name)]
                    entities.append(
                        {
                            "name": ent.name,
                            "attr_count": ent.attr_count,
                            "required_count": ent.required_count,
                            "status": m.status,
                            "tier": m.tier or None,
                            "models": m.models,
                            "modules": m.modules,
                            "candidates": m.candidates,
                            "note": m.note or None,
                            "doc": ent.doc_excerpt or None,
                        }
                    )
            abes.append(
                {
                    "name": row.abe.name,
                    "qualified": row.abe.qualified,
                    "parent": row.abe.parent,
                    "status": row.status,
                    "mapped": row.mapped,
                    "total": row.total,
                    "ratio": round(row.ratio, 4),
                    "models": row.models,
                    "modules": row.modules,
                    "tmf_apis": row.tmf_apis,
                    "notes": row.notes or None,
                    "entities": entities,
                }
            )
        domains.append({"name": domain, "abes": abes})

    payload = {
        "generator": "tools/gen_sid_coverage.py",
        "sid_source": {
            "file": "GB922_Information_Framework_SID_Excel_v25.5.xlsx",
            "version": SID_VERSION,
        },
        "stats": stats,
        "native_extended": native_extended,
        "domains": domains,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def emit_csv(
    matches: list[EntityMatch], out_path: Path, include_patterns_entities: bool
) -> None:
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["domain", "abe", "entity", "status", "tier", "models", "modules"])
        for m in matches:
            if m.entity.domain == PATTERNS_DOMAIN and not include_patterns_entities:
                continue
            writer.writerow(
                [
                    m.entity.domain,
                    m.entity.abe,
                    m.entity.name,
                    m.status,
                    m.tier,
                    "|".join(m.models),
                    "|".join(m.modules),
                ]
            )


def emit_todo(
    matches: list[EntityMatch],
    idx: MatchIndex,
    out_path: Path,
) -> None:
    key_to_models: dict[str, set[str]] = {}
    for index in (idx.name_index, idx.desc_index):
        for key, models in index.items():
            key_to_models.setdefault(key, set()).update(m.name for m in models)
    all_keys = sorted(key_to_models)

    ambiguous = []
    unmatched = []
    for m in matches:
        if m.entity.domain == PATTERNS_DOMAIN:
            continue
        key = f"{m.entity.abe}/{m.entity.name}"
        stub = {"odoo_models": [], "note": ""}
        if m.status == "ambiguous":
            ambiguous.append({"key": key, "candidates": m.candidates, "stub": stub})
        elif m.status in ("unmatched", "proxy"):
            close = difflib.get_close_matches(norm(m.entity.name), all_keys, n=3, cutoff=0.85)
            suggestions = sorted({name for c in close for name in key_to_models[c]})
            unmatched.append({"key": key, "suggestions": suggestions, "stub": stub})

    payload = {
        "_comment": (
            "Review queue generated by tools/gen_sid_coverage.py. Resolve entries "
            "by copying the key + a filled stub into entity_overrides of "
            "mappings/sid_abe_map.json, then regenerate."
        ),
        "ambiguous": ambiguous,
        "unmatched_with_suggestions": unmatched,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Generate the SID ABE -> Odoo model coverage matrix."
    )
    parser.add_argument("--excel", default=DEFAULT_EXCEL, help="GB922 SID Excel path.")
    parser.add_argument("--repo-root", default=str(repo_root), help="Addons repo root.")
    parser.add_argument("--out-dir", default="", help="Output dir (default: <repo>/docs).")
    parser.add_argument(
        "--overrides", default="", help="Curated map (default: <repo>/mappings/sid_abe_map.json)."
    )
    parser.add_argument(
        "--fail-on-unmapped",
        action="store_true",
        help="Exit 1 if any business-domain ABE has no coverage.",
    )
    parser.add_argument(
        "--strict-overrides",
        action="store_true",
        help="Treat override validation problems as errors.",
    )
    parser.add_argument(
        "--include-patterns-entities",
        action="store_true",
        help="Include Patterns-domain entities in JSON/CSV outputs.",
    )
    parser.add_argument("--dump-sid", action="store_true", help="Print SID counts and exit.")
    parser.add_argument("--dump-models", action="store_true", help="Print scan counts and exit.")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except AttributeError:
        pass
    args = parse_args()
    repo_root = Path(args.repo_root)
    out_dir = Path(args.out_dir) if args.out_dir else repo_root / "docs"
    overrides_path = (
        Path(args.overrides) if args.overrides else repo_root / "mappings" / "sid_abe_map.json"
    )

    sid = load_sid_workbook(Path(args.excel))
    if args.dump_sid:
        entities = sid.entities()
        print(f"domains={len(sid.domains)} abes={len(sid.abes)} entities={len(entities)}")
        for domain in sid.domains:
            n_abes = sum(1 for a in sid.abes if a.domain == domain)
            n_ents = sum(len(a.entities) for a in sid.abes if a.domain == domain)
            print(f"  {domain}: abes={n_abes} entities={n_ents}")
        return 0

    tmf_models, native_extended = scan_odoo_models(repo_root)
    if args.dump_models:
        addons = sorted({m.addon for m in tmf_models})
        print(f"tmf_models={len(tmf_models)} addons={len(addons)}")
        print("native_extended:")
        for model, mods in native_extended.items():
            print(f"  {model}: {len(mods)} addons")
        return 0

    overrides = load_overrides(overrides_path, sid, tmf_models, native_extended)
    if overrides.problems:
        for problem in overrides.problems:
            print(f"OVERRIDE {'ERROR' if args.strict_overrides else 'WARNING'}: {problem}",
                  file=sys.stderr)
        if args.strict_overrides:
            return 2

    idx = build_match_index(tmf_models)
    matches = match_entities(sid, idx, overrides, native_extended)
    abe_rows = compute_abe_rows(sid, matches, overrides, native_extended)

    business = [m for m in matches if m.entity.domain != PATTERNS_DOMAIN]
    tier_counts = {t: sum(1 for m in business if m.tier == t)
                   for t in ("curated", "high", "medium", "inherited")}
    status_counts = {s: 0 for s in ("covered", "partial", "missing", "na")}
    for row in abe_rows:
        if row.abe.domain != PATTERNS_DOMAIN:
            status_counts[row.status] += 1
    ambiguous = sum(1 for m in business if m.status == "ambiguous")
    unmatched = sum(1 for m in business if m.status in ("unmatched", "proxy"))

    stats = {
        "domains": len(sid.domains),
        "abes": len(sid.abes),
        "entities": len(sid.entities()),
        "tmf_models": len(tmf_models),
        "business_entities": len(business),
        "entity_tiers": tier_counts,
        "entities_ambiguous": ambiguous,
        "entities_unmatched": unmatched,
        "abe_status_business": status_counts,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    emit_markdown(sid, abe_rows, matches, out_dir / "SID_ABE_COVERAGE_MATRIX.md")
    emit_json(
        sid, abe_rows, matches, tmf_models, native_extended, stats,
        out_dir / "sid_abe_coverage.json", args.include_patterns_entities,
    )
    emit_csv(matches, out_dir / "sid_abe_coverage.csv", args.include_patterns_entities)
    emit_todo(matches, idx, out_dir / "sid_abe_coverage.todo.json")

    print(
        f"SID: {stats['domains']} domains, {stats['abes']} ABEs, "
        f"{stats['entities']} entities | scan: {stats['tmf_models']} TMF models"
    )
    print(
        "match (business domains): "
        + " ".join(f"{k}={v}" for k, v in tier_counts.items())
        + f" ambiguous={ambiguous} unmatched={unmatched}"
    )
    print(
        "ABE status (business domains): "
        + " ".join(f"{k}={v}" for k, v in status_counts.items())
    )
    print(f"wrote 4 files to {out_dir}")

    if args.fail_on_unmapped and status_counts["missing"] > 0:
        print(f"FAIL: {status_counts['missing']} ABEs without coverage", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
