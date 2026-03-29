"""
mapping_engine.py — TMF Open API Declarative Field Mapping Engine
=================================================================

Consumes YAML mapping files (see FIELD_MAPPING_SCHEMA.md) and provides:
  - to_tmf_json(record, mapping_id)  : Odoo record dict → TMF JSON payload dict
  - sync_to_odoo(tmf_payload, mapping_id) : TMF JSON payload → Odoo field values dict

Design decisions:
  - Standalone: no Odoo dependency. Records are plain Python dicts.
  - Extensible: custom transforms registered via TRANSFORM_REGISTRY.
  - Strict: unknown field types raise MappingError to catch schema typos early.
  - Lazy: YAML is loaded once and cached; re-use engine instances.

Usage:
    engine = MappingEngine("mappings/tmf620_product_catalog.yaml")
    tmf_json = engine.to_tmf_json(record_dict, mapping_id="product_offering")
    odoo_vals = engine.sync_to_odoo(tmf_payload, mapping_id="product_offering")
"""

from __future__ import annotations

import os
import re
import logging
from typing import Any, Callable, Dict, List, Optional

try:
    import yaml
except ImportError as e:
    raise ImportError(
        "PyYAML is required: pip install pyyaml"
    ) from e

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MappingError(Exception):
    """Raised when a mapping rule cannot be applied (schema error or missing data)."""


class SchemaVersionError(MappingError):
    """Raised when the YAML spec_version is incompatible with this engine."""


# ---------------------------------------------------------------------------
# Transform registry
# ---------------------------------------------------------------------------

def _transform_date_iso(v: Any) -> Optional[str]:
    """Format a date/datetime object or ISO string to ISO8601 date string."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _transform_datetime_iso(v: Any) -> Optional[str]:
    """Format a datetime to ISO8601 with Z suffix."""
    if v is None:
        return None
    s = _transform_date_iso(v)
    if s and "T" not in s:
        s += "T00:00:00Z"
    return s


#: Registry of named transforms. Add custom transforms here or via register_transform().
TRANSFORM_REGISTRY: Dict[str, Callable[[Any], Any]] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "capitalize": lambda v: str(v).capitalize() if v else v,
    "upper": lambda v: str(v).upper() if v else v,
    "lower": lambda v: str(v).lower() if v else v,
    "strip": lambda v: str(v).strip() if v else v,
    "date_iso": _transform_date_iso,
    "datetime_iso": _transform_datetime_iso,
}


def register_transform(name: str, fn: Callable[[Any], Any]) -> None:
    """Register a custom transform function by name."""
    TRANSFORM_REGISTRY[name] = fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENGINE_SPEC_VERSION = (1, 0)  # (major, minor)
REQUIRED_HEADER_FIELDS = ("schema_version", "spec_version", "odoo_version")
EXPECTED_ODOO_VERSION = ">=19.0"


def _check_spec_version(spec_version: str) -> None:
    """Validate the YAML spec_version against this engine version."""
    try:
        parts = [int(x) for x in str(spec_version).split(".")]
        major = parts[0]
        minor = parts[1] if len(parts) > 1 else 0
    except (ValueError, IndexError) as exc:
        raise SchemaVersionError(f"Invalid spec_version: {spec_version!r}") from exc

    eng_major, eng_minor = ENGINE_SPEC_VERSION
    if major != eng_major:
        raise SchemaVersionError(
            f"Incompatible schema major version {major} (engine supports {eng_major}.x)"
        )
    if minor > eng_minor:
        logger.warning(
            "Schema spec_version %s is newer than engine %s.%s — some features may be ignored.",
            spec_version, eng_major, eng_minor,
        )


def validate_mapping_header(mapping: dict, expected_odoo_version: Optional[str] = None) -> None:
    """Ensure the mapping file declares the required header fields."""
    if not isinstance(mapping, dict):
        raise ValueError("Mapping header must be a dictionary.")

    for field in REQUIRED_HEADER_FIELDS:
        if field not in mapping:
            raise ValueError(f"Mapping header missing required '{field}' field")
        value = mapping.get(field)
        value_str = value.strip() if isinstance(value, str) else str(value).strip() if value is not None else ""
        if not value_str:
            raise ValueError(f"Mapping header missing required '{field}' field")

    if expected_odoo_version:
        declared = str(mapping.get("odoo_version", "")).strip()
        if declared != expected_odoo_version:
            raise SchemaVersionError(
                f"Mapping odoo_version {declared!r} does not match required {expected_odoo_version}"
            )


def load_mapping(yaml_path: str, expected_odoo_version: str = EXPECTED_ODOO_VERSION) -> dict:
    """Load a YAML file and validate its header."""
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Mapping file not found: {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Mapping file {yaml_path} must contain a mapping dictionary at the root.")
    validate_mapping_header(data, expected_odoo_version=expected_odoo_version)
    return data


def _apply_transform(value: Any, transform_name: Optional[str]) -> Any:
    """Apply a named transform from the registry. Returns value unchanged if transform is None."""
    if transform_name is None:
        return value
    fn = TRANSFORM_REGISTRY.get(transform_name)
    if fn is None:
        raise MappingError(f"Unknown transform: {transform_name!r}")
    try:
        return fn(value)
    except Exception as exc:
        raise MappingError(f"Transform {transform_name!r} failed on {value!r}: {exc}") from exc


def _get_nested(record: dict, dotted_path: str) -> Any:
    """
    Read a (possibly dotted) field path from a nested dict.
    e.g. "product_specification_id.tmf_id" traverses record["product_specification_id"]["tmf_id"]
    Returns None if any intermediate key is missing or falsy.
    """
    parts = dotted_path.split(".")
    current = record
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _set_nested(target: dict, tmf_key: str, value: Any) -> None:
    """Set a value in the target dict under tmf_key. Supports simple keys only (no dot paths)."""
    target[tmf_key] = value


def _is_truthy(value: Any) -> bool:
    """Return True if value is considered 'truthy' in the mapping sense (not None, not False, not empty)."""
    if value is None:
        return False
    if isinstance(value, (list, dict, str)) and not value:
        return False
    return bool(value)


# ---------------------------------------------------------------------------
# Direction filtering
# ---------------------------------------------------------------------------

def _field_applies(field_def: dict, direction: str, mapping_direction: str) -> bool:
    """
    Return True if this field entry should be processed in the given direction.
    direction: "to_tmf" or "to_odoo"
    """
    effective = field_def.get("direction", mapping_direction)
    return effective == "bidirectional" or effective == direction


# ---------------------------------------------------------------------------
# Field processors — to_tmf
# ---------------------------------------------------------------------------

def _process_direct_to_tmf(field: dict, record: dict, output: dict) -> None:
    """Process a 'direct' field entry in the to_tmf direction."""
    odoo_field = field.get("odoo_field")
    tmf_key = field.get("tmf_key")
    if not odoo_field or not tmf_key:
        raise MappingError(f"'direct' field missing odoo_field or tmf_key: {field}")

    value = _get_nested(record, odoo_field)
    value = _apply_transform(value, field.get("transform"))

    if field.get("if_truthy") and not _is_truthy(value):
        return

    if not _is_truthy(value) and "default" in field:
        value = field["default"]

    _set_nested(output, tmf_key, value)


def _process_fallback_to_tmf(field: dict, record: dict, output: dict) -> None:
    """Process a 'fallback' entry: try each source in order, use first truthy value."""
    tmf_key = field.get("tmf_key")
    sources = field.get("sources", [])
    if not tmf_key:
        raise MappingError(f"'fallback' field missing tmf_key: {field}")

    value = None
    for source in sources:
        # Source may be an odoo_field or a literal default
        if "default" in source and not source.get("odoo_field"):
            value = source["default"]
            break
        raw = _get_nested(record, source["odoo_field"])
        raw = _apply_transform(raw, source.get("transform"))
        if _is_truthy(raw):
            value = raw
            break

    if field.get("if_truthy") and not _is_truthy(value):
        return

    _set_nested(output, tmf_key, value)


def _process_literal_to_tmf(field: dict, record: dict, output: dict) -> None:
    """Process a 'literal' entry: inject a hardcoded value or read from a dotted field path."""
    tmf_key = field.get("tmf_key")
    if not tmf_key:
        raise MappingError(f"'literal' field missing tmf_key: {field}")

    if "value_from_field" in field:
        # value_from_field supports dotted paths into the record
        raw = _get_nested(record, field["value_from_field"])
        value = raw
    else:
        value = field.get("value")

    # If a 'wrap' dict is specified, nest the value inside a dict with extra keys
    wrap = field.get("wrap")
    if wrap and value is not None:
        wrapped = dict(wrap)
        wrapped["id"] = value  # convention: wrap injects 'id' from the value
        value = wrapped

    if field.get("if_truthy") and not _is_truthy(value):
        return

    _set_nested(output, tmf_key, value)


def _process_value_map_to_tmf(field: dict, record: dict, output: dict) -> None:
    """Process a 'value_map' entry in the to_tmf direction."""
    odoo_field = field.get("odoo_field")
    tmf_key = field.get("tmf_key")
    if not odoo_field or not tmf_key:
        raise MappingError(f"'value_map' field missing odoo_field or tmf_key: {field}")

    source_value = _get_nested(record, odoo_field)

    # Support both flat map and directional map
    raw_map = field.get("map", {})
    if "to_tmf" in raw_map:
        mapping_dict = raw_map["to_tmf"]
    else:
        mapping_dict = raw_map  # flat map assumed to be to_tmf

    defaults = field.get("default", {})
    default_val = defaults.get("to_tmf") if isinstance(defaults, dict) else defaults

    # Handle multi-value sources (e.g. multiple Odoo states map to same TMF status)
    # Keys in the map may be space/comma-separated tuples encoded as single keys
    mapped = mapping_dict.get(str(source_value)) if source_value is not None else None
    if mapped is None and default_val is not None:
        mapped = default_val

    if field.get("if_truthy") and not _is_truthy(mapped):
        return

    _set_nested(output, tmf_key, mapped)


def _process_many2one_ref_to_tmf(field: dict, record: dict, output: dict) -> None:
    """
    Process a 'many2one_ref' entry in the to_tmf direction.
    Serializes a related record dict to a TMF reference object.
    """
    odoo_field = field.get("odoo_field")
    tmf_key = field.get("tmf_key")
    ref_type = field.get("ref_type", "")
    id_field = field.get("id_field", "tmf_id")
    name_field = field.get("name_field", "name")
    href_template = field.get("href_template", "")

    if not odoo_field or not tmf_key:
        raise MappingError(f"'many2one_ref' field missing odoo_field or tmf_key: {field}")

    related = _get_nested(record, odoo_field)

    if field.get("if_truthy") and not _is_truthy(related):
        return

    if not isinstance(related, dict):
        # If it's a scalar (bare ID), wrap it
        if related is not None:
            related = {"id": related}
        else:
            _set_nested(output, tmf_key, None)
            return

    # Resolve ID: prefer tmf_id, fall back to str(id)
    ref_id = related.get(id_field) or str(related.get("id", ""))
    ref_name = related.get(name_field)

    ref_obj: Dict[str, Any] = {"id": ref_id}
    if ref_name:
        ref_obj["name"] = ref_name

    if href_template:
        base_url = os.environ.get("TMF_BASE_URL", "")
        href = base_url + href_template.format(id=ref_id)
        ref_obj["href"] = href

    ref_obj["@type"] = f"{ref_type}Ref"
    ref_obj["@referredType"] = ref_type

    _set_nested(output, tmf_key, ref_obj)


def _process_related_party_to_tmf(field: dict, record: dict, output: dict) -> None:
    """
    Process a 'related_party' entry in the to_tmf direction.
    Reads a partner dict (or list of partner dicts) from the record and emits relatedParty array.
    """
    tmf_key = field.get("tmf_key", "relatedParty")
    odoo_field = field.get("odoo_field")
    role = field.get("role", "")
    role_filter = field.get("role_filter")  # only emit parties with this role

    if not odoo_field:
        raise MappingError(f"'related_party' field missing odoo_field: {field}")

    raw = _get_nested(record, odoo_field)
    if field.get("if_truthy") and not _is_truthy(raw):
        return

    # Normalize: accept a single partner dict, a list of dicts, or a list of IDs
    if raw is None:
        return
    if isinstance(raw, dict):
        partners = [raw]
    elif isinstance(raw, list):
        partners = raw
    else:
        # Bare ID
        partners = [{"id": raw}]

    parties = []
    for p in partners:
        if not isinstance(p, dict):
            p = {"id": p}
        party_role = p.get("role", role)
        if role_filter and party_role != role_filter:
            continue
        party: Dict[str, Any] = {
            "id": p.get("tmf_id") or str(p.get("id", "")),
            "@type": "RelatedParty",
        }
        if p.get("name"):
            party["name"] = p["name"]
        if party_role:
            party["role"] = party_role
        parties.append(party)

    if parties:
        _set_nested(output, tmf_key, parties)


def _process_nested_object_to_tmf(field: dict, record: dict, output: dict) -> None:
    """
    Process a 'nested_object' entry in the to_tmf direction.
    Recursively processes sub-fields into a nested dict.
    """
    tmf_key = field.get("tmf_key")
    sub_fields = field.get("fields", [])
    guard_field = field.get("if_truthy_field")

    if not tmf_key:
        raise MappingError(f"'nested_object' field missing tmf_key: {field}")

    if guard_field:
        guard_val = _get_nested(record, guard_field)
        if not _is_truthy(guard_val):
            return

    nested_output: Dict[str, Any] = {}
    for sub in sub_fields:
        _dispatch_to_tmf(sub, record, nested_output, mapping_direction="to_tmf")

    if nested_output:
        _set_nested(output, tmf_key, nested_output)


def _process_conditional_block_to_tmf(field: dict, record: dict, output: dict) -> None:
    """
    Process a 'conditional_block' entry in the to_tmf direction.
    Evaluates branches in order; executes the first matching branch's emit list.
    """
    branches = field.get("branches", [])

    for branch in branches:
        guard_field = branch.get("if_truthy_field")
        guard_value = branch.get("if_equals_field")
        guard_expected = branch.get("equals")

        condition_met = False
        if guard_field:
            val = _get_nested(record, guard_field)
            condition_met = _is_truthy(val)
        elif guard_value and guard_expected is not None:
            val = _get_nested(record, guard_value)
            condition_met = (val == guard_expected)
        else:
            # 'else' branch — no condition key present
            condition_met = True

        if condition_met:
            for emit_field in branch.get("emit", []):
                _dispatch_to_tmf(emit_field, record, output, mapping_direction="to_tmf")
            break  # stop at first matching branch (if/elif semantics)


# ---------------------------------------------------------------------------
# Field processors — to_odoo (sync direction)
# ---------------------------------------------------------------------------

def _process_direct_to_odoo(field: dict, payload: dict, output: dict) -> None:
    """Process a 'direct' field entry in the to_odoo direction."""
    odoo_field = field.get("odoo_field")
    tmf_key = field.get("tmf_key")
    if not odoo_field or not tmf_key:
        raise MappingError(f"'direct' field missing odoo_field or tmf_key: {field}")

    if field.get("required") and tmf_key not in payload:
        raise MappingError(f"Required TMF key {tmf_key!r} not found in payload")

    value = payload.get(tmf_key)
    value = _apply_transform(value, field.get("transform"))

    if not _is_truthy(value) and "default" in field:
        value = field["default"]

    output[odoo_field] = value


def _process_fallback_to_odoo(field: dict, payload: dict, output: dict) -> None:
    """Process a 'fallback' entry in the to_odoo direction."""
    odoo_field = field.get("odoo_field")
    sources = field.get("sources", [])

    # In to_odoo direction, sources are tmf_keys (or defaults)
    value = None
    for source in sources:
        if "default" in source and not source.get("tmf_key"):
            value = source["default"]
            break
        key = source.get("tmf_key") or source.get("odoo_field")  # fallback to odoo_field for compat
        if key and key in payload:
            raw = payload[key]
            raw = _apply_transform(raw, source.get("transform"))
            if _is_truthy(raw):
                value = raw
                break

    if odoo_field:
        output[odoo_field] = value


def _process_value_map_to_odoo(field: dict, payload: dict, output: dict) -> None:
    """Process a 'value_map' entry in the to_odoo direction."""
    odoo_field = field.get("odoo_field")
    tmf_key = field.get("tmf_key")
    if not odoo_field or not tmf_key:
        raise MappingError(f"'value_map' field missing odoo_field or tmf_key: {field}")

    tmf_value = payload.get(tmf_key)

    raw_map = field.get("map", {})
    if "to_odoo" in raw_map:
        mapping_dict = raw_map["to_odoo"]
    else:
        mapping_dict = raw_map

    defaults = field.get("default", {})
    default_val = defaults.get("to_odoo") if isinstance(defaults, dict) else defaults

    mapped = mapping_dict.get(str(tmf_value)) if tmf_value is not None else None
    if mapped is None and default_val is not None:
        mapped = default_val

    output[odoo_field] = mapped


def _process_many2one_ref_to_odoo(field: dict, payload: dict, output: dict, model_env: Optional[dict] = None) -> None:
    """
    Process a 'many2one_ref' entry in the to_odoo direction.
    Resolves a TMF reference object back to an Odoo record ID.

    model_env: optional dict mapping model names to lists of record dicts
                (for standalone testing; in Odoo, use actual model search).
    """
    odoo_field = field.get("odoo_field")
    tmf_key = field.get("tmf_key")
    ref_odoo_model = field.get("ref_odoo_model")
    id_field = field.get("id_field", "tmf_id")

    if not odoo_field or not tmf_key:
        raise MappingError(f"'many2one_ref' field missing odoo_field or tmf_key: {field}")

    ref_obj = payload.get(tmf_key)
    if not ref_obj:
        output[odoo_field] = False
        return

    ref_id = ref_obj.get("id") if isinstance(ref_obj, dict) else str(ref_obj)
    ref_name = ref_obj.get("name") if isinstance(ref_obj, dict) else None

    # Resolution strategy: use model_env if provided (for standalone); otherwise return a lookup hint
    resolved_id = None
    if model_env and ref_odoo_model and ref_odoo_model in model_env:
        records = model_env[ref_odoo_model]
        # 1. Match by tmf_id
        for rec in records:
            if rec.get(id_field) == ref_id:
                resolved_id = rec["id"]
                break
        # 2. Match by integer id
        if resolved_id is None and ref_id and str(ref_id).isdigit():
            target = int(ref_id)
            for rec in records:
                if rec.get("id") == target:
                    resolved_id = rec["id"]
                    break
        # 3. Match by name
        if resolved_id is None and ref_name:
            for rec in records:
                if rec.get("name") == ref_name:
                    resolved_id = rec["id"]
                    break

    if resolved_id is not None:
        output[odoo_field] = resolved_id
    else:
        # Return a resolution hint dict so the caller can do their own lookup
        output[odoo_field] = {
            "_unresolved": True,
            "tmf_id": ref_id,
            "name": ref_name,
            "model": ref_odoo_model,
        }


def _process_related_party_to_odoo(field: dict, payload: dict, output: dict, model_env: Optional[dict] = None) -> None:
    """
    Process a 'related_party' entry in the to_odoo direction.
    Resolves relatedParty entries to res.partner records.

    Returns a list of resolution hints if model_env is not provided.
    """
    tmf_key = field.get("tmf_key", "relatedParty")
    odoo_field = field.get("odoo_field")
    role_filter = field.get("role_filter")

    parties = payload.get(tmf_key, [])
    if not parties:
        return

    if not isinstance(parties, list):
        parties = [parties]

    resolved = []
    for entry in parties:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("id") or "")
        pname = str(entry.get("name") or "")
        prole = entry.get("role", "")

        if role_filter and prole != role_filter:
            continue

        partner_id = None
        if model_env and "res.partner" in model_env:
            partners = model_env["res.partner"]
            for p in partners:
                if p.get("tmf_id") == pid:
                    partner_id = p["id"]
                    break
            if partner_id is None and pid.isdigit():
                target = int(pid)
                for p in partners:
                    if p.get("id") == target:
                        partner_id = p["id"]
                        break
            if partner_id is None and pname:
                for p in partners:
                    if p.get("name") == pname:
                        partner_id = p["id"]
                        break

        if partner_id is not None:
            resolved.append(partner_id)
        else:
            resolved.append({"_unresolved": True, "tmf_id": pid, "name": pname, "role": prole})

    if odoo_field:
        # For Many2one: use the first resolved partner
        output[odoo_field] = resolved[0] if resolved else False
    else:
        # For Many2many: return all resolved partners as a list
        output[tmf_key + "_resolved"] = resolved


# ---------------------------------------------------------------------------
# Dispatch tables
# ---------------------------------------------------------------------------

_TO_TMF_HANDLERS = {
    "direct": _process_direct_to_tmf,
    "fallback": _process_fallback_to_tmf,
    "literal": _process_literal_to_tmf,
    "value_map": _process_value_map_to_tmf,
    "many2one_ref": _process_many2one_ref_to_tmf,
    "related_party": _process_related_party_to_tmf,
    "nested_object": _process_nested_object_to_tmf,
    "conditional_block": _process_conditional_block_to_tmf,
}

_TO_ODOO_HANDLERS = {
    "direct": _process_direct_to_odoo,
    "fallback": _process_fallback_to_odoo,
    "value_map": _process_value_map_to_odoo,
    "many2one_ref": _process_many2one_ref_to_odoo,
    "related_party": _process_related_party_to_odoo,
    # literal and nested_object have no to_odoo action by default
}


def _dispatch_to_tmf(field: dict, record: dict, output: dict, mapping_direction: str) -> None:
    """Dispatch a single field entry to its to_tmf handler."""
    ftype = field.get("type")
    if not ftype:
        raise MappingError(f"Field entry missing 'type': {field}")
    if not _field_applies(field, "to_tmf", mapping_direction):
        return
    handler = _TO_TMF_HANDLERS.get(ftype)
    if handler is None:
        raise MappingError(f"Unknown field type for to_tmf: {ftype!r}")
    handler(field, record, output)


def _dispatch_to_odoo(field: dict, payload: dict, output: dict, mapping_direction: str, model_env: Optional[dict] = None) -> None:
    """Dispatch a single field entry to its to_odoo handler."""
    ftype = field.get("type")
    if not ftype:
        raise MappingError(f"Field entry missing 'type': {field}")
    if not _field_applies(field, "to_odoo", mapping_direction):
        return
    handler = _TO_ODOO_HANDLERS.get(ftype)
    if handler is None:
        # Types like 'literal' and 'nested_object' are to_tmf only — skip silently
        logger.debug("No to_odoo handler for field type %r — skipping.", ftype)
        return

    # Inject model_env for handlers that need it
    if ftype in ("many2one_ref", "related_party"):
        handler(field, payload, output, model_env=model_env)
    else:
        handler(field, payload, output)


# ---------------------------------------------------------------------------
# MappingEngine
# ---------------------------------------------------------------------------

class MappingEngine:
    """
    Loads a YAML mapping file and exposes to_tmf_json() and sync_to_odoo().

    The engine is stateless after initialization — safe to share across threads.
    """

    def __init__(self, yaml_path: str) -> None:
        """Load and validate a YAML mapping file."""
        self._expected_odoo_version = EXPECTED_ODOO_VERSION
        data = load_mapping(yaml_path, expected_odoo_version=self._expected_odoo_version)

        spec_version = data["spec_version"]
        _check_spec_version(spec_version)

        self._mapping_data = data
        self._meta = {
            "schema_version": data["schema_version"],
            "spec_version": spec_version,
            "odoo_version": data.get("odoo_version"),
            "tmf_spec": data.get("tmf_spec"),
            "tmf_version": data.get("tmf_version"),
            "description": data.get("description"),
        }

        # Index mappings by ID for fast lookup
        self._mappings: Dict[str, dict] = {}
        for m in data.get("mappings", []):
            mid = m.get("id")
            if not mid:
                raise MappingError("Each mapping entry must have an 'id' field")
            self._mappings[mid] = m

        logger.debug(
            "Loaded mapping file %s: spec=%s mappings=%s",
            yaml_path, spec_version, list(self._mappings.keys())
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_tmf_json(self, record: dict, mapping_id: str) -> dict:
        """
        Serialize an Odoo record dict to a TMF JSON payload dict.

        Args:
            record: Odoo record as a flat or nested dict.
            mapping_id: ID of the mapping entry to use (from the YAML 'id' field).

        Returns:
            TMF JSON dict. Callers may serialize to JSON with json.dumps().
        """
        validate_mapping_header(self._mapping_data, expected_odoo_version=self._expected_odoo_version)
        mapping = self._get_mapping(mapping_id)
        direction = mapping.get("direction", "bidirectional")
        fields = mapping.get("fields", [])

        output: Dict[str, Any] = {}
        for field in fields:
            try:
                _dispatch_to_tmf(field, record, output, mapping_direction=direction)
            except MappingError:
                raise
            except Exception as exc:
                raise MappingError(
                    f"Error processing field {field} in mapping {mapping_id!r}: {exc}"
                ) from exc

        return output

    def sync_to_odoo(
        self,
        tmf_payload: dict,
        mapping_id: str,
        model_env: Optional[dict] = None,
    ) -> dict:
        """
        Convert a TMF JSON payload dict to an Odoo field values dict.

        Args:
            tmf_payload: Incoming TMF JSON as a Python dict.
            mapping_id: ID of the mapping entry to use.
            model_env: Optional dict mapping Odoo model names to lists of record dicts,
                       used for Many2one and RelatedParty resolution in standalone mode.
                       In production Odoo, implement a custom resolver instead.

        Returns:
            Odoo vals dict suitable for model.write(vals) or model.create(vals).
            Unresolved relational fields are returned as dicts with '_unresolved: True'
            so the caller can handle the lookup.
        """
        validate_mapping_header(self._mapping_data, expected_odoo_version=self._expected_odoo_version)
        mapping = self._get_mapping(mapping_id)
        direction = mapping.get("direction", "bidirectional")
        fields = mapping.get("fields", [])

        output: Dict[str, Any] = {}
        for field in fields:
            try:
                _dispatch_to_odoo(field, tmf_payload, output, mapping_direction=direction, model_env=model_env)
            except MappingError:
                raise
            except Exception as exc:
                raise MappingError(
                    f"Error processing field {field} in mapping {mapping_id!r}: {exc}"
                ) from exc

        return output

    def list_mappings(self) -> List[str]:
        """Return the list of available mapping IDs in this file."""
        return list(self._mappings.keys())

    @property
    def meta(self) -> dict:
        """File-level metadata (spec_version, tmf_spec, odoo_version, etc.)."""
        return dict(self._meta)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_mapping(self, mapping_id: str) -> dict:
        mapping = self._mappings.get(mapping_id)
        if mapping is None:
            raise MappingError(
                f"Mapping {mapping_id!r} not found. Available: {list(self._mappings.keys())}"
            )
        return mapping


# ---------------------------------------------------------------------------
# CLI self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 3:
        print("Usage: mapping_engine.py <yaml_file> <mapping_id> [to_tmf|to_odoo]")
        print("  Reads JSON record from stdin and prints the result.")
        sys.exit(1)

    yaml_file = sys.argv[1]
    mapping_id = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "to_tmf"

    engine = MappingEngine(yaml_file)
    input_data = json.load(sys.stdin)

    if mode == "to_tmf":
        result = engine.to_tmf_json(input_data, mapping_id)
    elif mode == "to_odoo":
        result = engine.sync_to_odoo(input_data, mapping_id)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))
