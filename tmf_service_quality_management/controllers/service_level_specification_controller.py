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
)

RESOURCE = "serviceLevelSpecification"
BASE_PATH = f"{API_BASE}/{RESOURCE}"

TMF_TO_ODOO = {
    "id": "tmf_id",
    "name": "name",
}


class TMF657ServiceLevelSpecificationController(http.Controller):

    @http.route(f"{BASE_PATH}", type="http", auth="public", methods=["GET"], csrf=False)
    def list_sls(self, **kwargs):
        env = request.env["tmf.service.level.specification"].sudo()
        wanted = _fields_param()

        domain = []
        for key, val in request.httprequest.args.items():
            if key in ("fields",):
                continue
            if key in TMF_TO_ODOO:
                domain.append((TMF_TO_ODOO[key], "=", val))

        recs = env.search(domain, limit=200)
        payload = [_apply_fields_filter(r.to_tmf_dict(), wanted) for r in recs]
        return _json_response(payload, status=200)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_sls(self, rid, **kwargs):
        env = request.env["tmf.service.level.specification"].sudo()
        wanted = _fields_param()

        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"{RESOURCE} {rid} not found")

        payload = _apply_fields_filter(rec.to_tmf_dict(), wanted)
        return _json_response(payload, status=200)

    @http.route(f"{BASE_PATH}", type="http", auth="public", methods=["POST"], csrf=False)
    def create_sls(self, **kwargs):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="INVALID_JSON", details=str(e))

        # Mandatory per TMF657 guide: name, relatedServiceLevelObjective
        missing = [k for k in ("name", "relatedServiceLevelObjective") if k not in body]
        if missing:
            return _error(400, "Bad Request", code="MISSING_MANDATORY", details={"missing": missing})

        new_id = body.get("id") or _new_id()
        href = f"{BASE_PATH}/{new_id}"

        vals = {
            "tmf_id": new_id,
            "href": href,
            "name": body["name"],
            "description": body.get("description"),
            "valid_for_json": json.dumps(body.get("validFor")) if body.get("validFor") else False,
            "related_service_level_objective_json": json.dumps(body["relatedServiceLevelObjective"]),
            "raw_json": json.dumps(body, ensure_ascii=False),
        }

        try:
            rec = request.env["tmf.service.level.specification"].sudo().create(vals)
        except Exception as e:
            return _error(500, "Internal Error", code="INTERNAL_ERROR", details=str(e))

        return _json_response(rec.to_tmf_dict(), status=201)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_sls(self, rid, **kwargs):
        ctype = (request.httprequest.headers.get("Content-Type") or "").lower()
        if "application/merge-patch+json" not in ctype and "application/json" not in ctype:
            return _error(415, "Unsupported Media Type", code="UNSUPPORTED_MEDIA_TYPE",
                          details="Use application/merge-patch+json")

        try:
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="INVALID_JSON", details=str(e))

        env = request.env["tmf.service.level.specification"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"{RESOURCE} {rid} not found")

        # Non-patchable: href, id, validFor
        forbidden = [k for k in ("href", "id", "validFor") if k in patch]
        if forbidden:
            return _error(400, "Bad Request", code="NON_PATCHABLE", details={"nonPatchable": forbidden})

        current = rec.to_tmf_dict()
        merged = _merge_patch(current, patch)

        vals = {}
        if "name" in merged:
            vals["name"] = merged.get("name")
        if "description" in merged:
            vals["description"] = merged.get("description")

        if "relatedServiceLevelObjective" in merged:
            vals["related_service_level_objective_json"] = (
                json.dumps(merged.get("relatedServiceLevelObjective"))
                if merged.get("relatedServiceLevelObjective") is not None else False
            )

        vals["raw_json"] = json.dumps(merged, ensure_ascii=False)

        try:
            rec.write(vals)
        except Exception as e:
            return _error(500, "Internal Error", code="INTERNAL_ERROR", details=str(e))

        return _json_response(rec.to_tmf_dict(), status=200)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_sls(self, rid, **kwargs):
        env = request.env["tmf.service.level.specification"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"{RESOURCE} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)
