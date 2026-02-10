# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
from datetime import datetime

API_BASE_1 = "/tmf-api/serviceProblemManagement/v5"   # what your latest CTK run uses
API_BASE_2 = "/tmf-api/ServiceProblemManagement/v5"   # some CTK configs use this (case-sensitive)

NON_PATCHABLE = {
    "id", "href", "@type", "@baseType", "@schemaLocation",
    "originatingSystem", "trackingRecord", "errorMessage", "firstAlert",
}

LIST_FILTER_MAP = {
    "category": ("category", "=", "str"),
    "description": ("description", "=", "str"),
    "reason": ("reason", "=", "str"),
    "status": ("status", "=", "str"),
    "priority": ("priority", "=", "int"),
    # CTK uses creationDate/lastUpdate as filters too:
    "creationDate": ("creation_date", "=", "dt"),
    "lastUpdate": ("last_update", "=", "dt"),
}

def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)

def _read_json_body():
    raw = request.httprequest.data or b"{}"
    return json.loads(raw.decode("utf-8"))

def _dt_parse(v):
    if not v:
        return None
    # accept ISO strings with Z or offset; keep it simple for CTK equality filters
    try:
        return fields.Datetime.from_string(v)
    except Exception:
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None

def _apply_fields_filter(obj: dict, fields_param):
    """
    TMF 'fields' typically keeps id/href/@type plus requested fields.
    """
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    always = {"id", "href", "@type"}
    out = {k: v for k, v in obj.items() if k in always or k in wanted}
    return out

def _as_json_text(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value

def _require(cond, msg):
    if not cond:
        raise ValueError(msg)

def _domain_from_params(params):
    domain = []
    for qp, (field, op, typ) in LIST_FILTER_MAP.items():
        if qp not in params:
            continue
        raw = params.get(qp)
        if typ == "int":
            try:
                raw = int(raw)
            except Exception:
                continue
        elif typ == "dt":
            dt = _dt_parse(raw)
            if dt is None:
                continue
            raw = dt
        domain.append((field, op, raw))
    return domain


class TMF656Controller(http.Controller):

    # ----------------------------
    # ServiceProblem
    # ----------------------------
    @http.route([f"{API_BASE_1}/serviceProblem", f"{API_BASE_2}/serviceProblem"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def list_service_problem(self, **params):
        domain = _domain_from_params(params)
        recs = request.env["tmf.service.problem"].sudo().search(domain)
        payload = [_apply_fields_filter(r.to_tmf_json(), params.get("fields")) for r in recs]
        return _json_response(payload, status=200)

    @http.route([f"{API_BASE_1}/serviceProblem/<string:rid>", f"{API_BASE_2}/serviceProblem/<string:rid>"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_service_problem(self, rid, **params):
        rec = request.env["tmf.service.problem"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_response({"error": {"status": 404, "reason": "Not Found"}}, status=404)
        return _json_response(_apply_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route([f"{API_BASE_1}/serviceProblem", f"{API_BASE_2}/serviceProblem"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def post_service_problem(self, **params):
        try:
            data = _read_json_body()

            # Mandatory fields
            _require(data.get("@type") == "ServiceProblem", "TMF656 POST: '@type' must be 'ServiceProblem'")
            _require(data.get("category"), "TMF656 POST: 'category' is mandatory")
            _require(data.get("description"), "TMF656 POST: 'description' is mandatory")
            _require(data.get("priority") is not None, "TMF656 POST: 'priority' is mandatory")
            _require(data.get("reason"), "TMF656 POST: 'reason' is mandatory")

            op = data.get("originatorParty")
            _require(isinstance(op, dict), "TMF656 POST: 'originatorParty' must be an object")

            vals = {
                "tmf_type": "ServiceProblem",
                "category": data.get("category"),
                "description": data.get("description"),
                "priority": data.get("priority"),
                "reason": data.get("reason"),
                "status": data.get("status") or "acknowledged",
                "originator_party_json": _as_json_text(op),
                "name": data.get("name"),
                "originating_system": data.get("originatingSystem"),
                "problem_escalation": data.get("problemEscalation"),
                "status_change_reason": data.get("statusChangeReason"),
                "impact_importance_factor": data.get("impactImportanceFactor"),
            }

            # Dates (optional)
            if data.get("creationDate"):
                vals["creation_date"] = _dt_parse(data.get("creationDate"))
            if data.get("lastUpdate"):
                vals["last_update"] = _dt_parse(data.get("lastUpdate"))
            if data.get("resolutionDate"):
                vals["resolution_date"] = _dt_parse(data.get("resolutionDate"))
            if data.get("statusChangeDate"):
                vals["status_change_date"] = _dt_parse(data.get("statusChangeDate"))

            # 0..* arrays (store as JSON)
            def set_json(field, key):
                if key in data:
                    vals[field] = _as_json_text(data[key])

            set_json("affected_location_json", "affectedLocation")
            set_json("affected_resource_json", "affectedResource")
            set_json("affected_service_json", "affectedService")
            set_json("characteristic_json", "characteristic")
            set_json("external_identifier_json", "externalIdentifier")
            set_json("note_json", "note")
            set_json("parent_problem_json", "parentProblem")
            set_json("related_entity_json", "relatedEntity")
            set_json("related_event_json", "relatedEvent")
            set_json("related_party_json", "relatedParty")
            set_json("root_cause_resource_json", "rootCauseResource")
            set_json("root_cause_service_json", "rootCauseService")
            set_json("sla_violation_json", "slaViolation")
            set_json("trouble_ticket_json", "troubleTicket")
            set_json("underlying_alarm_json", "underlyingAlarm")
            set_json("underlying_problem_json", "underlyingProblem")
            set_json("error_message_json", "errorMessage")
            set_json("tracking_record_json", "trackingRecord")

            # 0..1 objects
            if "firstAlert" in data:
                vals["first_alert_json"] = _as_json_text(data["firstAlert"])
            if "responsibleParty" in data:
                vals["responsible_party_json"] = _as_json_text(data["responsibleParty"])
            if "impactPattern" in data:
                vals["impact_pattern_json"] = _as_json_text(data["impactPattern"])

            rec = request.env["tmf.service.problem"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        except Exception as e:
            return _json_response({"error": {"status": 400, "reason": str(e)}}, status=400)

    @http.route([f"{API_BASE_1}/serviceProblem/<string:rid>", f"{API_BASE_2}/serviceProblem/<string:rid>"],
                type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_service_problem(self, rid, **params):
        try:
            rec = request.env["tmf.service.problem"].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not rec:
                return _json_response({"error": {"status": 404, "reason": "Not Found"}}, status=404)

            data = _read_json_body() or {}

            # CTK may include @type in PATCH payload. Accept it if correct.
            if "@type" in data:
                if data["@type"] != "ServiceProblem":
                    raise ValueError("TMF656 PATCH: '@type' must be 'ServiceProblem'")
                data.pop("@type", None)


            # Reject non-patchable fields
            for k in data.keys():
                if k in NON_PATCHABLE:
                    raise ValueError(f"TMF656 PATCH: '{k}' is not patchable")

            vals = {}

            # patchable scalar fields
            scalar_map = {
                "category": "category",
                "description": "description",
                "priority": "priority",
                "reason": "reason",
                "status": "status",
                "name": "name",
                "problemEscalation": "problem_escalation",
                "statusChangeReason": "status_change_reason",
                "impactImportanceFactor": "impact_importance_factor",
            }
            for k, f in scalar_map.items():
                if k in data:
                    vals[f] = data[k]

            # patch dates
            if "resolutionDate" in data:
                vals["resolution_date"] = _dt_parse(data.get("resolutionDate"))
            if "statusChangeDate" in data:
                vals["status_change_date"] = _dt_parse(data.get("statusChangeDate"))

            # patch JSON fields
            json_map = {
                "originatorParty": "originator_party_json",
                "affectedLocation": "affected_location_json",
                "affectedResource": "affected_resource_json",
                "affectedService": "affected_service_json",
                "characteristic": "characteristic_json",
                "externalIdentifier": "external_identifier_json",
                "note": "note_json",
                "parentProblem": "parent_problem_json",
                "relatedEntity": "related_entity_json",
                "relatedEvent": "related_event_json",
                "relatedParty": "related_party_json",
                "rootCauseResource": "root_cause_resource_json",
                "rootCauseService": "root_cause_service_json",
                "slaViolation": "sla_violation_json",
                "troubleTicket": "trouble_ticket_json",
                "underlyingAlarm": "underlying_alarm_json",
                "underlyingProblem": "underlying_problem_json",
                "responsibleParty": "responsible_party_json",
                "impactPattern": "impact_pattern_json",
            }
            for k, f in json_map.items():
                if k in data:
                    vals[f] = _as_json_text(data[k])

            # update lastUpdate automatically
            vals["last_update"] = fields.Datetime.now()

            if vals:
                rec.sudo().write(vals)

            return _json_response(rec.to_tmf_json(), status=200)

        except Exception as e:
            return _json_response({"error": {"status": 400, "reason": str(e)}}, status=400)

    @http.route([f"{API_BASE_1}/serviceProblem/<string:rid>", f"{API_BASE_2}/serviceProblem/<string:rid>"],
                type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_service_problem(self, rid, **params):
        rec = request.env["tmf.service.problem"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if rec:
            rec.unlink()
        return request.make_response("", status=204)

    # ----------------------------
    # Task resources (TMF656)
    # ----------------------------
    def _task_list(self, model, fields_param=None):
        recs = request.env[model].sudo().search([])
        return _json_response([_apply_fields_filter(r.to_tmf_json(), fields_param) for r in recs], status=200)

    def _task_get(self, model, rid, fields_param=None):
        rec = request.env[model].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_response({"error": {"status": 404, "reason": "Not Found"}}, status=404)
        return _json_response(_apply_fields_filter(rec.to_tmf_json(), fields_param), status=200)

    # ---- ProblemAcknowledgement ----
    @http.route([f"{API_BASE_1}/ProblemAcknowledgement", f"{API_BASE_2}/ProblemAcknowledgement"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def list_problem_ack(self, **params):
        return self._task_list("tmf.problem.acknowledgement", params.get("fields"))

    @http.route([f"{API_BASE_1}/ProblemAcknowledgement/<string:rid>", f"{API_BASE_2}/ProblemAcknowledgement/<string:rid>"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_problem_ack(self, rid, **params):
        return self._task_get("tmf.problem.acknowledgement", rid, params.get("fields"))

    @http.route([f"{API_BASE_1}/ProblemAcknowledgement", f"{API_BASE_2}/ProblemAcknowledgement"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def post_problem_ack(self, **params):
        try:
            data = _read_json_body()

            _require(data.get("@type") == "ProblemAcknowledgement", "POST ProblemAcknowledgement: '@type' must be 'ProblemAcknowledgement'")
            _require(isinstance(data.get("problem"), list) and len(data["problem"]) > 0, "POST ProblemAcknowledgement: 'problem' must be a non-empty array")

            vals = {
                "tmf_type": "ProblemAcknowledgement",
                "state": data.get("state") or "acknowledged",
                "problem_json": _as_json_text(data.get("problem")),
                "ack_problem_json": _as_json_text(data.get("ackProblem")),
                "tracking_record_json": _as_json_text(data.get("trackingRecord")),
            }
            rec = request.env["tmf.problem.acknowledgement"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        except Exception as e:
            return _json_response({"error": {"status": 400, "reason": str(e)}}, status=400)

    # ---- ProblemUnacknowledgement ----
    @http.route([f"{API_BASE_1}/ProblemUnacknowledgement", f"{API_BASE_2}/ProblemUnacknowledgement"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def list_problem_unack(self, **params):
        return self._task_list("tmf.problem.unacknowledgement", params.get("fields"))

    @http.route([f"{API_BASE_1}/ProblemUnacknowledgement/<string:rid>", f"{API_BASE_2}/ProblemUnacknowledgement/<string:rid>"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_problem_unack(self, rid, **params):
        return self._task_get("tmf.problem.unacknowledgement", rid, params.get("fields"))

    @http.route([f"{API_BASE_1}/ProblemUnacknowledgement", f"{API_BASE_2}/ProblemUnacknowledgement"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def post_problem_unack(self, **params):
        try:
            data = _read_json_body()

            _require(data.get("@type") == "ProblemUnacknowledgement", "POST ProblemUnacknowledgement: '@type' must be 'ProblemUnacknowledgement'")
            _require(isinstance(data.get("problem"), list) and len(data["problem"]) > 0, "POST ProblemUnacknowledgement: 'problem' must be a non-empty array")

            vals = {
                "tmf_type": "ProblemUnacknowledgement",
                "state": data.get("state") or "acknowledged",
                "problem_json": _as_json_text(data.get("problem")),
                "unack_problem_json": _as_json_text(data.get("unackProblem")),
                "tracking_record_json": _as_json_text(data.get("trackingRecord")),
            }
            rec = request.env["tmf.problem.unacknowledgement"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        except Exception as e:
            return _json_response({"error": {"status": 400, "reason": str(e)}}, status=400)

    # ---- problemGroup ----
    @http.route([f"{API_BASE_1}/problemGroup", f"{API_BASE_2}/problemGroup"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def list_problem_group(self, **params):
        return self._task_list("tmf.problem.group", params.get("fields"))

    @http.route([f"{API_BASE_1}/problemGroup/<string:rid>", f"{API_BASE_2}/problemGroup/<string:rid>"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_problem_group(self, rid, **params):
        return self._task_get("tmf.problem.group", rid, params.get("fields"))

    @http.route([f"{API_BASE_1}/problemGroup", f"{API_BASE_2}/problemGroup"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def post_problem_group(self, **params):
        try:
            data = _read_json_body()

            _require(data.get("@type") == "ProblemGroup", "POST problemGroup: '@type' must be 'ProblemGroup'")
            _require(isinstance(data.get("childProblem"), list) and len(data["childProblem"]) > 0, "POST problemGroup: 'childProblem' must be a non-empty array")
            _require(isinstance(data.get("parentProblem"), dict), "POST problemGroup: 'parentProblem' must be an object")

            vals = {
                "tmf_type": "ProblemGroup",
                "state": data.get("state") or "acknowledged",
                "child_problem_json": _as_json_text(data.get("childProblem")),
                "parent_problem_json": _as_json_text(data.get("parentProblem")),
            }
            rec = request.env["tmf.problem.group"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        except Exception as e:
            return _json_response({"error": {"status": 400, "reason": str(e)}}, status=400)

    # ---- problemUngroup ----
    @http.route([f"{API_BASE_1}/problemUngroup", f"{API_BASE_2}/problemUngroup"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def list_problem_ungroup(self, **params):
        return self._task_list("tmf.problem.ungroup", params.get("fields"))

    @http.route([f"{API_BASE_1}/problemUngroup/<string:rid>", f"{API_BASE_2}/problemUngroup/<string:rid>"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_problem_ungroup(self, rid, **params):
        return self._task_get("tmf.problem.ungroup", rid, params.get("fields"))

    @http.route([f"{API_BASE_1}/problemUngroup", f"{API_BASE_2}/problemUngroup"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def post_problem_ungroup(self, **params):
        try:
            data = _read_json_body()

            _require(data.get("@type") == "ProblemUngroup", "POST problemUngroup: '@type' must be 'ProblemUngroup'")
            _require(isinstance(data.get("childProblem"), list) and len(data["childProblem"]) > 0, "POST problemUngroup: 'childProblem' must be a non-empty array")
            _require(isinstance(data.get("parentProblem"), dict), "POST problemUngroup: 'parentProblem' must be an object")

            vals = {
                "tmf_type": "ProblemUngroup",
                "state": data.get("state") or "acknowledged",
                "child_problem_json": _as_json_text(data.get("childProblem")),
                "parent_problem_json": _as_json_text(data.get("parentProblem")),
            }
            rec = request.env["tmf.problem.ungroup"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        except Exception as e:
            return _json_response({"error": {"status": 400, "reason": str(e)}}, status=400)
