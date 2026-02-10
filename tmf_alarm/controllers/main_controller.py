# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import uuid
from datetime import datetime, timezone


API_BASE = "/tmf-api/alarmManagement/v5"
RESOURCE = "alarm"
BASE_PATH = f"{API_BASE}/{RESOURCE}"

DT_KEYS = {"alarmRaisedTime", "alarmReportingTime", "alarmChangedTime", "alarmClearedTime"}


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _error(status, reason, code=None, details=None):
    payload = {"error": {"status": status, "reason": reason}}
    if code:
        payload["error"]["code"] = code
    if details:
        payload["error"]["details"] = details
    return _json_response(payload, status=status)


def _parse_json_body():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _require(data: dict, keys):
    missing = []
    for k in keys:
        v = data.get(k, None)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(k)
    return missing


def _safe(fn):
    try:
        return fn()
    except Exception as e:
        # CTK expects JSON, not HTML 500
        return _error(400, "Request failed", details={"exception": str(e)})


def _to_odoo_dt(value):
    """
    Accept RFC3339/ISO values like 2019-07-03T03:32:17.235Z and return Odoo datetime string.
    Returns None for empty/invalid/undefined.
    """
    if value is None:
        return None

    s = str(value).strip()
    if not s or s.lower() in ("undefined", "null", "none"):
        return None

    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # If no timezone, treat as UTC
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None

    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _tmf_to_odoo_vals(data: dict):
    """
    Map TMF642 (camelCase) JSON to Odoo fields (snake_case).
    Includes datetime normalization.
    """
    mapping = {
        # mandatory / core
        "alarmRaisedTime": "alarm_raised_time",
        "alarmReportingTime": "alarm_reporting_time",
        "alarmChangedTime": "alarm_changed_time",
        "alarmClearedTime": "alarm_cleared_time",
        "alarmType": "alarm_type",
        "perceivedSeverity": "perceived_severity",
        "probableCause": "probable_cause",
        "sourceSystemId": "source_system_id",
        "state": "state",
        "ackState": "ack_state",

        # optional scalars
        "ackSystemId": "ack_system_id",
        "ackUserId": "ack_user_id",
        "alarmDetails": "alarm_details",
        "alarmEscalation": "alarm_escalation",
        "alarmedObjectType": "alarmed_object_type",
        "clearSystemId": "clear_system_id",
        "clearUserId": "clear_user_id",
        "externalAlarmId": "external_alarm_id",
        "isRootCause": "is_root_cause",
        "plannedOutageIndicator": "planned_outage_indicator",
        "proposedRepairedActions": "proposed_repaired_actions",
        "reportingSystemId": "reporting_system_id",
        "serviceAffecting": "service_affecting",
        "specificProblem": "specific_problem",

        # complex json
        "affectedService": "affected_service",
        "alarmedObject": "alarmed_object",
        "comment": "comment",
        "correlatedAlarm": "correlated_alarm",
        "crossedThresholdInformation": "crossed_threshold_information",
        "parentAlarm": "parent_alarm",
        "place": "place",
    }

    vals = {}
    for tmf_key, odoo_key in mapping.items():
        if tmf_key not in data:
            continue

        v = data[tmf_key]
        if tmf_key in DT_KEYS:
            v = _to_odoo_dt(v)

        # For optional strings, avoid writing non-string junk like False
        if odoo_key in {
            "ack_system_id", "ack_user_id", "alarm_details", "alarmed_object_type",
            "clear_system_id", "clear_user_id", "external_alarm_id",
            "proposed_repaired_actions", "reporting_system_id", "specific_problem",
            "probable_cause", "source_system_id",
        }:
            if v is None:
                continue
            if isinstance(v, str):
                v = v.strip()
                if not v:
                    continue
            else:
                # don't store booleans/objects into Char fields
                continue

        vals[odoo_key] = v

    return vals


def _apply_fields_filter(obj: dict, fields_param):
    """
    TMF 'fields' query param: comma-separated list of attributes to keep.
    Must always keep id, href, @type for schema.
    """
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    wanted |= {"id", "href", "@type"}
    return {k: v for k, v in obj.items() if k in wanted}


def _extract_alarm_ids(alarm_refs):
    ids = []
    if not isinstance(alarm_refs, list):
        return ids
    for item in alarm_refs:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids


class TMF642AlarmController(http.Controller):

    @http.route(BASE_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_alarms(self, **params):
        def run():
            env = request.env["tmf.alarm"].sudo()
            domain = []

            if params.get("state") and params["state"].lower() != "undefined":
                domain.append(("state", "=", params["state"]))
            if params.get("alarmType") and params["alarmType"].lower() != "undefined":
                domain.append(("alarm_type", "=", params["alarmType"]))
            if params.get("perceivedSeverity") and params["perceivedSeverity"].lower() != "undefined":
                domain.append(("perceived_severity", "=", params["perceivedSeverity"]))
            if params.get("sourceSystemId") and params["sourceSystemId"].lower() != "undefined":
                domain.append(("source_system_id", "=", params["sourceSystemId"]))
            if params.get("ackState") and params["ackState"].lower() != "undefined":
                domain.append(("ack_state", "=", params["ackState"]))

            if params.get("alarmRaisedTime"):
                od = _to_odoo_dt(params["alarmRaisedTime"])
                if od:
                    domain.append(("alarm_raised_time", "=", od))

            records = env.search(domain)
            payload = [_apply_fields_filter(r.to_tmf_json(), params.get("fields")) for r in records]
            return _json_response(payload, status=200)

        return _safe(run)

    @http.route(f"{BASE_PATH}/<string:alarm_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_alarm(self, alarm_id, **params):
        def run():
            env = request.env["tmf.alarm"].sudo()
            rec = env.search([("tmf_id", "=", alarm_id)], limit=1)
            if not rec and alarm_id.isdigit():
                rec = env.browse(int(alarm_id))
            if not rec or not rec.exists():
                return _error(404, "Alarm not found")
            payload = _apply_fields_filter(rec.to_tmf_json(), params.get("fields"))
            return _json_response(payload, status=200)

        return _safe(run)

    @http.route(BASE_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_alarm(self, **_params):
        def run():
            data = _parse_json_body()
            if data is None or not isinstance(data, dict):
                return _error(400, "Invalid JSON body")

            missing = _require(
                data,
                ["alarmRaisedTime", "alarmType", "perceivedSeverity", "probableCause", "sourceSystemId"]
            )
            if missing:
                return _error(400, "Missing mandatory attributes", details={"missing": missing})

            data.setdefault("state", "raised")
            data.setdefault("ackState", "unacknowledged")
            data.setdefault("alarmReportingTime", data.get("alarmRaisedTime"))

            vals = _tmf_to_odoo_vals(data)
            rec = request.env["tmf.alarm"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        return _safe(run)

    @http.route(f"{BASE_PATH}/<string:alarm_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_alarm(self, alarm_id, **_params):
        def run():
            data = _parse_json_body()
            if data is None or not isinstance(data, dict):
                return _error(400, "Invalid JSON body")

            env = request.env["tmf.alarm"].sudo()
            rec = env.search([("tmf_id", "=", alarm_id)], limit=1)
            if not rec and alarm_id.isdigit():
                rec = env.browse(int(alarm_id))
            if not rec or not rec.exists():
                return _error(404, "Alarm not found")

            vals = _tmf_to_odoo_vals(data)
            if not vals:
                return _error(400, "No updatable attributes provided")

            rec.write(vals)
            return _json_response(rec.to_tmf_json(), status=200)

        return _safe(run)

    @http.route(f"{BASE_PATH}/<string:alarm_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_alarm(self, alarm_id, **_params):
        def run():
            env = request.env["tmf.alarm"].sudo()
            rec = env.search([("tmf_id", "=", alarm_id)], limit=1)
            if not rec and alarm_id.isdigit():
                rec = env.browse(int(alarm_id))
            if not rec or not rec.exists():
                return _error(404, "Alarm not found")

            rec.unlink()
            return request.make_response("", status=204)

        return _safe(run)

    # ---- Tasks ----
    @http.route(f"{API_BASE}/ackAlarm", type="http", auth="public", methods=["POST"], csrf=False)
    def ack_alarm(self, **_params):
        def run():
            data = _parse_json_body()
            if data is None or not isinstance(data, dict):
                return _error(400, "Invalid JSON body")

            missing = _require(data, ["ackSystemId", "ackUserId", "alarmPattern"])
            if missing:
                return _error(400, "Missing mandatory attributes", details={"missing": missing})

            ids = _extract_alarm_ids(data.get("alarmPattern"))
            if not ids:
                return _error(400, "alarmPattern must contain at least one AlarmRef with an id")

            env = request.env["tmf.alarm"].sudo()
            recs = env.search([("tmf_id", "in", ids)])
            if not recs:
                recs = env.browse([int(x) for x in ids if x.isdigit()])

            now = fields.Datetime.now()
            for rec in recs:
                rec.write({
                    "ack_state": "acknowledged",
                    "ack_system_id": data["ackSystemId"],
                    "ack_user_id": data["ackUserId"],
                    "alarm_changed_time": now,
                })

            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "href": f"{API_BASE}/ackAlarm/{task_id}",
                "@type": "AckAlarm",
                "ackSystemId": data["ackSystemId"],
                "ackUserId": data["ackUserId"],
                "ackTime": data.get("ackTime"),
                "state": "done",
                "alarmPattern": data.get("alarmPattern", []),
                "ackedAlarm": [r.to_tmf_json() for r in recs],
            }
            return _json_response(payload, status=201)

        return _safe(run)

    @http.route(f"{API_BASE}/unAckAlarm", type="http", auth="public", methods=["POST"], csrf=False)
    def unack_alarm(self, **_params):
        def run():
            data = _parse_json_body()
            if data is None or not isinstance(data, dict):
                return _error(400, "Invalid JSON body")

            missing = _require(data, ["ackSystemId", "ackUserId", "alarmPattern"])
            if missing:
                return _error(400, "Missing mandatory attributes", details={"missing": missing})

            ids = _extract_alarm_ids(data.get("alarmPattern"))
            if not ids:
                return _error(400, "alarmPattern must contain at least one AlarmRef with an id")

            env = request.env["tmf.alarm"].sudo()
            recs = env.search([("tmf_id", "in", ids)])
            if not recs:
                recs = env.browse([int(x) for x in ids if x.isdigit()])

            now = fields.Datetime.now()
            for rec in recs:
                rec.write({
                    "ack_state": "unacknowledged",
                    "ack_system_id": data["ackSystemId"],
                    "ack_user_id": data["ackUserId"],
                    "alarm_changed_time": now,
                })

            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "href": f"{API_BASE}/unAckAlarm/{task_id}",
                "@type": "UnAckAlarm",
                "ackSystemId": data["ackSystemId"],
                "ackUserId": data["ackUserId"],
                "ackTime": data.get("ackTime"),
                "state": "done",
                "alarmPattern": data.get("alarmPattern", []),
                "unAckedAlarm": [r.to_tmf_json() for r in recs],
            }
            return _json_response(payload, status=201)

        return _safe(run)

    @http.route(f"{API_BASE}/clearAlarm", type="http", auth="public", methods=["POST"], csrf=False)
    def clear_alarm(self, **_params):
        def run():
            data = _parse_json_body()
            if data is None or not isinstance(data, dict):
                return _error(400, "Invalid JSON body")

            missing = _require(data, ["clearSystemId", "clearUserId", "alarmPattern"])
            if missing:
                return _error(400, "Missing mandatory attributes", details={"missing": missing})

            ids = _extract_alarm_ids(data.get("alarmPattern"))
            if not ids:
                return _error(400, "alarmPattern must contain at least one AlarmRef with an id")

            env = request.env["tmf.alarm"].sudo()
            recs = env.search([("tmf_id", "in", ids)])
            if not recs:
                recs = env.browse([int(x) for x in ids if x.isdigit()])

            now = fields.Datetime.now()
            for rec in recs:
                rec.write({
                    "state": "cleared",
                    "alarm_cleared_time": now,
                    "clear_system_id": data["clearSystemId"],
                    "clear_user_id": data["clearUserId"],
                    "alarm_changed_time": now,
                    "perceived_severity": "cleared",
                })

            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "href": f"{API_BASE}/clearAlarm/{task_id}",
                "@type": "ClearAlarm",
                "clearSystemId": data["clearSystemId"],
                "clearUserId": data["clearUserId"],
                "clearTime": data.get("clearTime"),
                "state": "done",
                "alarmPattern": data.get("alarmPattern", []),
                "clearedAlarm": [r.to_tmf_json() for r in recs],
            }
            return _json_response(payload, status=201)

        return _safe(run)

    @http.route(f"{API_BASE}/commentAlarm", type="http", auth="public", methods=["POST"], csrf=False)
    def comment_alarm(self, **_params):
        def run():
            data = _parse_json_body()
            if data is None or not isinstance(data, dict):
                return _error(400, "Invalid JSON body")

            missing = _require(data, ["alarmPattern", "comment"])
            if missing:
                return _error(400, "Missing mandatory attributes", details={"missing": missing})

            ids = _extract_alarm_ids(data.get("alarmPattern"))
            if not ids:
                return _error(400, "alarmPattern must contain at least one AlarmRef with an id")

            comment_obj = data.get("comment")
            if not isinstance(comment_obj, dict) or not comment_obj.get("comment"):
                return _error(400, "comment must be a Comment object with at least 'comment' text")

            env = request.env["tmf.alarm"].sudo()
            recs = env.search([("tmf_id", "in", ids)])
            if not recs:
                recs = env.browse([int(x) for x in ids if x.isdigit()])

            now = fields.Datetime.now()
            for rec in recs:
                existing = rec.comment or []
                existing.append({
                    "@type": "Comment",
                    "comment": comment_obj.get("comment"),
                    "systemId": comment_obj.get("systemId"),
                    "userId": comment_obj.get("userId"),
                    "time": comment_obj.get("time") or now.isoformat(),
                })
                rec.write({"comment": existing, "alarm_changed_time": now})

            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "href": f"{API_BASE}/commentAlarm/{task_id}",
                "@type": "CommentAlarm",
                "state": "done",
                "alarmPattern": data.get("alarmPattern", []),
                "comment": comment_obj,
                "commentedAlarm": [r.to_tmf_json() for r in recs],
            }
            return _json_response(payload, status=201)

        return _safe(run)
