# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

from .common import (
    API_BASE,
    _json_response,
    _error,
    _parse_json_body,
    _new_id,
    _fields_param,
    _apply_fields_filter,
    _merge_patch,
    _normalize_qp,
)

RESOURCE = "serviceLevelObjective"
BASE_PATH = f"{API_BASE}/{RESOURCE}"


# Map TMF query params / payload keys -> Odoo model fields
TMF_TO_ODOO = {
    "id": "tmf_id",
    "name": "name",
    "conformanceComparator": "conformance_comparator",
    "conformanceTarget": "conformance_target",
}


class TMF657ServiceLevelObjectiveController(http.Controller):

    @http.route(f"{BASE_PATH}", type="http", auth="public", methods=["GET"], csrf=False)
    def list_slo(self, **kwargs):
        env = request.env["tmf.service.level.objective"].sudo()
        wanted = _fields_param()

        domain = []
        for key, val in request.httprequest.args.items():
            if key in ("fields",):
                continue
            val = _normalize_qp(val)

            if key in TMF_TO_ODOO:
                domain.append((TMF_TO_ODOO[key], "=", val))


        recs = env.search(domain, limit=200)
        payload = [_apply_fields_filter(r.to_tmf_dict(), wanted) for r in recs]
        return _json_response(payload, status=200)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_slo(self, rid, **kwargs):
        env = request.env["tmf.service.level.objective"].sudo()
        wanted = _fields_param()

        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"{RESOURCE} {rid} not found")

        payload = _apply_fields_filter(rec.to_tmf_dict(), wanted)
        return _json_response(payload, status=200)

    @http.route(f"{BASE_PATH}", type="http", auth="public", methods=["POST"], csrf=False)
    def create_slo(self, **kwargs):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="INVALID_JSON", details=str(e))

        # Mandatory per TMF657 guide: conformanceComparator, conformanceTarget, serviceLevelObjectiveParameter
        missing = [k for k in ("conformanceComparator", "conformanceTarget", "serviceLevelObjectiveParameter") if k not in body]
        if missing:
            return _error(400, "Bad Request", code="MISSING_MANDATORY", details={"missing": missing})

        new_id = body.get("id") or _new_id()
        href = f"{BASE_PATH}/{new_id}"

        model = request.env["tmf.service.level.objective"].sudo()
        if "conformance_period_json" not in model._fields:
            return _error(500, "Internal Error", code="MODEL_FIELDS_MISSING",
                        details={"missing": "conformance_period_json", "loaded_fields": list(model._fields.keys())[:50]})


        vals = {
            "tmf_id": new_id,
            "href": href,
            "name": body.get("name"),

            "conformance_comparator": body["conformanceComparator"],
            "conformance_target": body["conformanceTarget"],

            "conformance_period_json": json.dumps(body.get("conformancePeriod")) if body.get("conformancePeriod") else False,
            "grace_times": body.get("graceTimes"),
            "threshold_target": body.get("thresholdTarget"),
            "tolerance_target": body.get("toleranceTarget"),
            "tolerance_period_json": json.dumps(body.get("tolerancePeriod")) if body.get("tolerancePeriod") else False,
            "valid_for_json": json.dumps(body.get("validFor")) if body.get("validFor") else False,

            "service_level_objective_parameter_json": json.dumps(body["serviceLevelObjectiveParameter"]),
            "service_level_objective_consequence_json": json.dumps(body.get("serviceLevelObjectiveConsequence"))
                if body.get("serviceLevelObjectiveConsequence") else False,

            "raw_json": json.dumps(body, ensure_ascii=False),
        }

        try:
            rec = request.env["tmf.service.level.objective"].sudo().create(vals)
        except Exception as e:
            # return JSON error (prevents CTK JSONError "Unexpected token <")
            return _error(500, "Internal Error", code="INTERNAL_ERROR", details=str(e))

        return _json_response(rec.to_tmf_dict(), status=201)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_slo(self, rid, **kwargs):
        ctype = (request.httprequest.headers.get("Content-Type") or "").lower()
        if "application/merge-patch+json" not in ctype and "application/json" not in ctype:
            return _error(415, "Unsupported Media Type", code="UNSUPPORTED_MEDIA_TYPE",
                          details="Use application/merge-patch+json")

        try:
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="INVALID_JSON", details=str(e))

        env = request.env["tmf.service.level.objective"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"{RESOURCE} {rid} not found")

        # Non-patchable per guide: href, id, validFor
        forbidden = [k for k in ("href", "id", "validFor") if k in patch]
        if forbidden:
            return _error(400, "Bad Request", code="NON_PATCHABLE", details={"nonPatchable": forbidden})

        current = rec.to_tmf_dict()
        merged = _merge_patch(current, patch)

        # Map merged TMF fields -> Odoo fields
        vals = {}

        if "name" in merged:
            vals["name"] = merged.get("name")

        if "conformanceComparator" in merged:
            vals["conformance_comparator"] = merged.get("conformanceComparator")

        if "conformanceTarget" in merged:
            vals["conformance_target"] = merged.get("conformanceTarget")

        if "graceTimes" in merged:
            vals["grace_times"] = merged.get("graceTimes")

        if "thresholdTarget" in merged:
            vals["threshold_target"] = merged.get("thresholdTarget")

        if "toleranceTarget" in merged:
            vals["tolerance_target"] = merged.get("toleranceTarget")

        if "conformancePeriod" in merged:
            vals["conformance_period_json"] = json.dumps(merged.get("conformancePeriod")) if merged.get("conformancePeriod") is not None else False

        if "tolerancePeriod" in merged:
            vals["tolerance_period_json"] = json.dumps(merged.get("tolerancePeriod")) if merged.get("tolerancePeriod") is not None else False

        if "serviceLevelObjectiveParameter" in merged:
            vals["service_level_objective_parameter_json"] = json.dumps(merged.get("serviceLevelObjectiveParameter")) if merged.get("serviceLevelObjectiveParameter") is not None else False

        if "serviceLevelObjectiveConsequence" in merged:
            vals["service_level_objective_consequence_json"] = json.dumps(merged.get("serviceLevelObjectiveConsequence")) if merged.get("serviceLevelObjectiveConsequence") is not None else False

        vals["raw_json"] = json.dumps(merged, ensure_ascii=False)

        try:
            rec.write(vals)
        except Exception as e:
            return _error(500, "Internal Error", code="INTERNAL_ERROR", details=str(e))

        return _json_response(rec.to_tmf_dict(), status=200)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_slo(self, rid, **kwargs):
        env = request.env["tmf.service.level.objective"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"{RESOURCE} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)
