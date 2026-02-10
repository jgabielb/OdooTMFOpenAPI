from odoo import http
from odoo.http import request
import json

API_BASE = "/tmf-api/resourceFunctionActivation/v4"
RESOURCE = "resourceFunction"
BASE_PATH = f"{API_BASE}/{RESOURCE}"

NON_PATCHABLE = {"id", "href", "usageState"}  # per TMF664

def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)

def _tmf_error(status, reason, code=None, details=None):
    # TMF docs don’t force a single error schema in this user guide; keep it consistent across APIs.
    err = {"status": status, "reason": reason}
    if code:
        err["code"] = code
    if details:
        err["details"] = details
    return _json_response({"error": err}, status=status)

def _parse_body():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None

class TMF664Controller(http.Controller):

    # LIST
    @http.route(BASE_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_resource_functions(self, **params):
        recs = request.env["tmf.resource.function"].sudo().search([])
        return _json_response([r.to_tmf_json() for r in recs], status=200)

    # RETRIEVE
    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource_function(self, rid, **params):
        rec = request.env["tmf.resource.function"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _tmf_error(404, f"ResourceFunction {rid} not found")
        return _json_response(rec.to_tmf_json(), status=200)

    # CREATE
    @http.route(BASE_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_resource_function(self, **params):
        data = _parse_body()
        if data is None:
            return _tmf_error(400, "Invalid JSON body")

        # TMF664 mandatory: name and resourceSpecification.id
        name = data.get("name")
        rs = data.get("resourceSpecification") or {}
        rs_id = rs.get("id") if isinstance(rs, dict) else None

        if not name:
            return _tmf_error(400, "Missing mandatory attribute: name")
        if not rs_id:
            return _tmf_error(400, "Missing mandatory attribute: resourceSpecification.id")

        try:
            vals = request.env["tmf.resource.function"].sudo().from_tmf_json(data)
            rec = request.env["tmf.resource.function"].sudo().create(vals)
            # return 201 on synchronous create (doc example)
            return _json_response(rec.to_tmf_json(), status=201)
        except Exception as e:
            return _tmf_error(400, "Create failed", details=str(e))

    # PATCH (merge-patch mandatory)
    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_resource_function(self, rid, **params):
        ct = (request.httprequest.headers.get("Content-Type") or "").lower()
        if "application/merge-patch+json" not in ct and "application/json" not in ct:
            return _tmf_error(415, "Unsupported Content-Type. Use application/merge-patch+json")

        patch = _parse_body()
        if patch is None or not isinstance(patch, dict):
            return _tmf_error(400, "Invalid JSON body")

        # TMF664 non-patchable fields
        illegal = [k for k in patch.keys() if k in NON_PATCHABLE]
        if illegal:
            return _tmf_error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")

        rec = request.env["tmf.resource.function"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _tmf_error(404, f"ResourceFunction {rid} not found")

        try:
            vals = request.env["tmf.resource.function"].sudo().from_tmf_json(patch, partial=True)
            rec.write(vals)
            return _json_response(rec.to_tmf_json(), status=200)
        except Exception as e:
            return _tmf_error(400, "Patch failed", details=str(e))

    # DELETE
    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_resource_function(self, rid, **params):
        rec = request.env["tmf.resource.function"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _tmf_error(404, f"ResourceFunction {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)
