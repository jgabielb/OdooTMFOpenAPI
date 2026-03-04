# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import uuid
from datetime import datetime

API_BASE = "/tmf-api/changeManagement/v4"
API_BASE_ALT = "/tmf-api/ChangeManagement/v4"
RESOURCE = "changeRequest"
BASE_PATH = f"{API_BASE}/{RESOURCE}"
BASE_PATH_ALT = f"{API_BASE_ALT}/{RESOURCE}"

MANDATORY_ON_CREATE = {
    "priority", "targetEntity", "specification",
    "plannedStartTime", "plannedEndTime", "requestType",
}

DT_FIELDS_MAP = {
    "plannedStartTime": "planned_start_time",
    "plannedEndTime": "planned_end_time",
    "requestDate": "request_date",
    "scheduledDate": "scheduled_date",
    "actualStartTime": "actual_start_time",
    "actualEndTime": "actual_end_time",
    "completionDate": "completion_date",
    "lastUpdateDate": "last_update_date",
    "statusChangeDate": "status_change_date",
}


# -------------------------
# Common helpers
# -------------------------
def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=headers,
        status=status,
    )


def _error(status, reason, code=None, details=None):
    payload = {"error": {"status": status, "reason": reason}}
    if code:
        payload["error"]["code"] = code
    if details:
        payload["error"]["details"] = details
    return _json_response(payload, status=status)


def _parse_json_body():
    raw = request.httprequest.data or b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _safe_parse_tmf_dt(value):
    """
    Accepts:
      - 2021-09-09T06:23:42.451Z
      - 2021-09-09T06:23:42Z
      - 2021-09-09T06:23:42.451+00:00
    Returns: datetime or None
    """
    if not value:
        return None

    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1]

    try:
        return fields.Datetime.to_datetime(s)
    except Exception:
        pass

    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _dt_to_tmf(value):
    if not value:
        return None
    return fields.Datetime.to_string(value)


def _loads_json(txt):
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def _to_tmf_payload(r):
    # CTK-friendly TMF ChangeRequest JSON (includes mandatory attrs)
    payload = {
        "id": r.tmf_id,
        "href": r.href,
        "priority": r.priority,
        "requestType": r.request_type,
        "plannedStartTime": _dt_to_tmf(r.planned_start_time),
        "plannedEndTime": _dt_to_tmf(r.planned_end_time),
        "targetEntity": _loads_json(r.target_entity_json) or [],
        "specification": _loads_json(r.specification_json) or {},
    }
    if r.status:
        payload["status"] = r.status
    return payload


class TMF655Controller(http.Controller):

    @http.route([BASE_PATH, BASE_PATH_ALT], type="http", auth="public", methods=["GET"], csrf=False)
    def list_change_requests(self, **params):
        dom = []

        # Equality filters used by CTK
        if params.get("id"):
            dom.append(("tmf_id", "=", params["id"]))
        if params.get("priority"):
            dom.append(("priority", "=", params["priority"]))
        if params.get("requestType"):
            dom.append(("request_type", "=", params["requestType"]))

        # DateTime filters (exact match) - SAFE (never 500)
        if params.get("plannedStartTime"):
            dt = _safe_parse_tmf_dt(params["plannedStartTime"])
            if dt is None:
                return _json_response([], status=200)
            dom.append(("planned_start_time", "=", dt))

        if params.get("plannedEndTime"):
            dt = _safe_parse_tmf_dt(params["plannedEndTime"])
            if dt is None:
                return _json_response([], status=200)
            dom.append(("planned_end_time", "=", dt))

        recs = request.env["tmf.change.request"].sudo().search(dom)

        # fields= support (basic; CTK uses fields=id, plannedStartTime, plannedEndTime, priority, requestType)
        fields_param = params.get("fields")
        if fields_param:
            wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
            out = []
            for r in recs:
                full = _to_tmf_payload(r)
                out.append({k: v for k, v in full.items() if k in wanted})
            return _json_response(out, status=200)

        return _json_response([_to_tmf_payload(r) for r in recs], status=200)

    @http.route([f"{BASE_PATH}/<string:cr_id>", f"{BASE_PATH_ALT}/<string:cr_id>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_change_request(self, cr_id, **params):
        r = request.env["tmf.change.request"].sudo().search([("tmf_id", "=", cr_id)], limit=1)
        if not r:
            return _error(404, "Not Found")
        return _json_response(_to_tmf_payload(r), status=200)

    @http.route([BASE_PATH, BASE_PATH_ALT], type="http", auth="public", methods=["POST"], csrf=False)
    def create_change_request(self, **params):
        body = _parse_json_body()
        if body is None:
            return _error(400, "Invalid JSON")

        missing = [k for k in MANDATORY_ON_CREATE if body.get(k) in (None, "", [])]
        if missing:
            return _error(400, "Missing mandatory attributes", details={"missing": missing})

        ps = _safe_parse_tmf_dt(body.get("plannedStartTime"))
        pe = _safe_parse_tmf_dt(body.get("plannedEndTime"))
        if ps is None or pe is None:
            return _error(400, "Invalid plannedStartTime/plannedEndTime")

        tmf_id = body.get("id") or f"cr_{uuid.uuid4().hex[:10]}"
        href = body.get("href") or f"{BASE_PATH}/{tmf_id}"

        vals = {
            "tmf_id": tmf_id,
            "href": href,
            "priority": body.get("priority"),
            "request_type": body.get("requestType"),
            "planned_start_time": ps,
            "planned_end_time": pe,
            "target_entity_json": json.dumps(body.get("targetEntity"), ensure_ascii=False),
            "specification_json": json.dumps(body.get("specification"), ensure_ascii=False),
        }

        # Optional datetimes if present (safe)
        for tmf_key, odoo_key in DT_FIELDS_MAP.items():
            if body.get(tmf_key):
                dt = _safe_parse_tmf_dt(body.get(tmf_key))
                if dt is not None:
                    vals[odoo_key] = dt

        # Optional simple fields
        if body.get("status") is not None:
            vals["status"] = body.get("status")
        if body.get("statusChangeReason") is not None:
            vals["status_change_reason"] = body.get("statusChangeReason")
        if body.get("channel") is not None:
            vals["channel"] = body.get("channel")
        if body.get("description") is not None:
            vals["description"] = body.get("description")
        if body.get("impact") is not None:
            vals["impact"] = body.get("impact")

        r = request.env["tmf.change.request"].sudo().create(vals)
        return _json_response(_to_tmf_payload(r), status=201)

    @http.route([f"{BASE_PATH}/<string:cr_id>", f"{BASE_PATH_ALT}/<string:cr_id>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_change_request(self, cr_id, **params):
        return _error(501, "Not Implemented")

    @http.route([f"{BASE_PATH}/<string:cr_id>", f"{BASE_PATH_ALT}/<string:cr_id>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_change_request(self, cr_id, **params):
        r = request.env["tmf.change.request"].sudo().search([("tmf_id", "=", cr_id)], limit=1)
        if not r:
            return _error(404, "Not Found")
        r.unlink()
        return request.make_response("", status=204)

