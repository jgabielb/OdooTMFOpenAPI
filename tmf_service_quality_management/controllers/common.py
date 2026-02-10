# -*- coding: utf-8 -*-
import json
import uuid
from odoo import http
from odoo.http import request

API_BASE = "/tmf-api/serviceQualityManagement/v4"


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _error(status, reason, code=None, details=None):
    payload = {"error": {"status": status, "reason": reason}}
    if code:
        payload["error"]["code"] = code
    if details is not None:
        payload["error"]["details"] = details
    return _json_response(payload, status=status)


def _parse_json_body():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON body: {e}")


def _new_id():
    return str(uuid.uuid4())


def _fields_param():
    fields_param = request.httprequest.args.get("fields")
    if not fields_param:
        return None
    wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
    return set(wanted) if wanted else None


def _apply_fields_filter(obj: dict, wanted_fields: set | None):
    if not wanted_fields:
        return obj
    # Always keep id/href if present (very common in TMF clients)
    keep = set(wanted_fields) | {"id", "href"}
    return {k: v for k, v in obj.items() if k in keep}


def _merge_patch(current: dict, patch: dict) -> dict:
    """
    RFC 7386 JSON Merge Patch (simplified):
    - If patch value is null -> remove key
    - If patch value is object -> recursively merge
    - Else -> replace
    """
    out = dict(current)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_patch(out[k], v)
        else:
            out[k] = v
    return out

def _normalize_qp(v: str) -> str:
    v = (v or "").strip()
    if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
        v = v[1:-1]
    return v
