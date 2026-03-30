from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


TREE_TAGS = {"tree", "list"}
COMMON_SEARCH_CANDIDATES = [
    "tmf_id",
    "name",
    "description",
    "partner_id",
    "customer_id",
    "party_id",
    "product_tmpl_id",
    "category",
    "state",
    "status",
    "create_date",
    "write_date",
]
GROUP_BY_CANDIDATES = [
    "state",
    "status",
    "partner_id",
    "customer_id",
    "category",
    "type",
    "create_date",
    "write_date",
]
DATE_FIELDS = {"create_date", "write_date", "date", "start_date", "end_date", "quote_date", "service_date"}


def indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def get_record_field(record: ET.Element, name: str) -> ET.Element | None:
    for fld in record.findall("field"):
        if fld.get("name") == name:
            return fld
    return None


def model_slug(model: str) -> str:
    return model.replace('.', '_')


def find_arch_root(record: ET.Element) -> ET.Element | None:
    arch = get_record_field(record, "arch")
    if arch is None:
        return None
    for child in list(arch):
        return child
    return None


def collect_list_fields(record: ET.Element) -> list[str]:
    root = find_arch_root(record)
    if root is None or root.tag not in TREE_TAGS:
        return []
    fields: list[str] = []
    for fld in root.findall("field"):
        name = fld.get("name")
        if name and name not in fields:
            fields.append(name)
    return fields


def existing_search_record(root: ET.Element, model: str) -> ET.Element | None:
    for record in root.findall("record"):
        model_f = get_record_field(record, "model")
        if model_f is None or (model_f.text or "").strip() != "ir.ui.view":
            continue
        rec_model_f = get_record_field(record, "model")
        view_model_f = None
        for fld in record.findall("field"):
            if fld.get("name") == "model":
                view_model_f = fld
        if view_model_f is None:
            continue
        # first field model is record model; second model field is actual model
        model_fields = [fld for fld in record.findall("field") if fld.get("name") == "model"]
        if len(model_fields) < 2:
            continue
        if (model_fields[1].text or "").strip() != model:
            continue
        arch_root = find_arch_root(record)
        if arch_root is not None and arch_root.tag == "search":
            return record
    return None


def create_search_record(model: str, action_name: str, list_fields: list[str]) -> ET.Element:
    rec = ET.Element("record", {"id": f"view_{model_slug(model)}_search_auto", "model": "ir.ui.view"})
    f_name = ET.SubElement(rec, "field", {"name": "name"})
    f_name.text = f"{model}.search.auto"
    f_model = ET.SubElement(rec, "field", {"name": "model"})
    f_model.text = model
    f_arch = ET.SubElement(rec, "field", {"name": "arch", "type": "xml"})
    search = ET.SubElement(f_arch, "search", {"string": f"Search {action_name or model}"})

    selected: list[str] = []
    for cand in COMMON_SEARCH_CANDIDATES:
        if cand in list_fields and cand not in selected:
            selected.append(cand)
    for fld in list_fields:
        if fld not in selected and len(selected) < 8:
            selected.append(fld)
    for name in selected:
        ET.SubElement(search, "field", {"name": name})

    # basic filters
    if "partner_id" in list_fields:
        ET.SubElement(search, "filter", {"string": "With Related Party", "name": "with_related_party", "domain": "[('partner_id', '!=', False)]"})
    if "customer_id" in list_fields:
        ET.SubElement(search, "filter", {"string": "With Customer", "name": "with_customer", "domain": "[('customer_id', '!=', False)]"})
    date_field = next((f for f in list_fields if f in DATE_FIELDS), None)
    if date_field:
        ET.SubElement(search, "filter", {"string": "Recent", "name": "recent", "domain": f"[('{date_field}', '>=', context_today())]"})

    ET.SubElement(search, "separator")
    for name in GROUP_BY_CANDIDATES:
        if name in list_fields:
            gb = name
            if name in {"create_date", "write_date"}:
                gb = f"{name}:day"
            label = f"Group by {name.replace('_', ' ').title()}"
            ET.SubElement(search, "filter", {"string": label, "name": f"group_{name}", "context": "{'group_by': '%s'}" % gb})
    return rec


def ensure_action_defaults(root: ET.Element) -> int:
    changed = 0
    for record in root.findall("record"):
        model_field = get_record_field(record, "model")
        if model_field is None or (model_field.text or "").strip() != "ir.actions.act_window":
            continue
        res_model_f = get_record_field(record, "res_model")
        name_f = get_record_field(record, "name")
        if res_model_f is None:
            continue
        model = (res_model_f.text or "").strip()
        action_name = (name_f.text or model).strip() if name_f is not None else model

        if get_record_field(record, "view_mode") is None:
            vm = ET.SubElement(record, "field", {"name": "view_mode"})
            vm.text = "list,form"
            changed += 1

        if get_record_field(record, "help") is None:
            help_f = ET.SubElement(record, "field", {"name": "help", "type": "html"})
            p1 = ET.SubElement(help_f, "p", {"class": "o_view_nocontent_smiling_face"})
            p1.text = f"Create your first {action_name[:-1] if action_name.endswith('s') else action_name}"
            p2 = ET.SubElement(help_f, "p")
            p2.text = f"Manage {action_name.lower()}, related entities, lifecycle state, and technical payload details from this screen."
            changed += 1

        search_f = get_record_field(record, "search_view_id")
        if search_f is None:
            # infer list fields from same model
            list_fields: list[str] = []
            for view_rec in root.findall("record"):
                rec_model = get_record_field(view_rec, "model")
                if rec_model is None or (rec_model.text or "").strip() != "ir.ui.view":
                    continue
                model_fields = [fld for fld in view_rec.findall("field") if fld.get("name") == "model"]
                if len(model_fields) < 2 or (model_fields[1].text or "").strip() != model:
                    continue
                fields_here = collect_list_fields(view_rec)
                if fields_here:
                    list_fields = fields_here
                    break
            search_rec = existing_search_record(root, model)
            if search_rec is None and list_fields:
                root.append(create_search_record(model, action_name, list_fields))
                search_id = f"view_{model_slug(model)}_search_auto"
                sf = ET.SubElement(record, "field", {"name": "search_view_id", "ref": search_id})
                changed += 2
            elif search_rec is not None:
                sid = search_rec.get("id")
                if sid:
                    ET.SubElement(record, "field", {"name": "search_view_id", "ref": sid})
                    changed += 1
    return changed


def process_file(path: Path, write: bool) -> int:
    tree = ET.parse(path)
    root = tree.getroot()
    changed = ensure_action_defaults(root)
    if write and changed:
        indent(root)
        tree.write(path, encoding="utf-8", xml_declaration=True)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply repo UI generator defaults to generated Odoo view XML files.")
    parser.add_argument("paths", nargs="+", help="Files or directories to process")
    parser.add_argument("--write", action="store_true", help="Write changes in place")
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("generated_views.xml")))
        elif p.is_file():
            files.append(p)
    total_changed = 0
    for file in files:
        changed = process_file(file, args.write)
        total_changed += changed
        print(f"{file}: changes={changed}")
    print(f"TOTAL_CHANGES={total_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
