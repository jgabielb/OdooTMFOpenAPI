# -*- coding: utf-8 -*-
import json
from datetime import datetime


def _now_z():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _as_dict(val):
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None
    return None


def _as_list(val):
    if val is None:
        return None
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            v = json.loads(s)
            return v if isinstance(v, list) else None
        except Exception:
            return None
    return None


def _json_dump(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _filter_top_level_fields(payload, fields_filter):
    """
    TMF rule used by CTK:
    - ?fields applies to FIRST-LEVEL attributes.
    - Always preserve: id, href, @type (CTK expects identifiers always).
    - If fields_filter empty => return full payload
    """
    if not fields_filter:
        return payload

    allowed = set(
        f.strip()
        for f in str(fields_filter).split(",")
        if f.strip()
    )

    # Always keep identifiers
    allowed.update({"id", "href", "@type"})

    return {k: v for k, v in payload.items() if k in allowed}


def _get_pagination(kwargs):
    def _int(x, default):
        try:
            return int(x)
        except Exception:
            return default

    offset = _int(kwargs.get("offset"), 0)
    limit = _int(kwargs.get("limit"), 100)
    if offset < 0:
        offset = 0
    if limit <= 0:
        limit = 100
    return offset, limit
