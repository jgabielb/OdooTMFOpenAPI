from odoo import http
from odoo.http import request
import json

BASE = "/tmf-api/serviceTestManagement/v4"
SERVICE_TEST = "serviceTest"
SERVICE_TEST_SPEC = "serviceTestSpecification"

SERVICE_TEST_PATH = f"{BASE}/{SERVICE_TEST}"
SERVICE_TEST_SPEC_PATH = f"{BASE}/{SERVICE_TEST_SPEC}"

# -------------------------
# Helpers
# -------------------------
def _json_response(payload=None, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    body = "" if payload is None else json.dumps(payload, ensure_ascii=False)
    return request.make_response(body, headers=headers, status=status)

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

def _apply_fields(obj, fields_param):
    """
    TMF 'fields' attribute selection: only first-level attributes.
    If fields not provided, return full object.
    """
    if not fields_param:
        return obj
    wanted = [f.strip() for f in str(fields_param).split(",") if f.strip()]
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in set(wanted)}

def _filter_records(model, params):
    """
    Minimal TMF filtering:
    - equality on first-level scalar fields: id, href, name, state, mode, version, lifecycleStatus, etc.
    This is enough for CTK queries like ?id=... or ?name=...
    """
    domain = []
    # map query param -> model field name
    mapping = {
        "id": "tmf_id",
        "name": "name",
        "state": "state",
        "mode": "mode",
        "version": "version",
        "lifecycleStatus": "lifecycle_status",
    }
    for qp, mf in mapping.items():
        if qp in params and params.get(qp) not in (None, ""):
            domain.append((mf, "=", params.get(qp)))
    return domain


# -------------------------
# Controllers
# -------------------------
class TMF653Controller(http.Controller):
    # ================
    # ServiceTest
    # ================
    @http.route(SERVICE_TEST_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_service_test(self, **params):
        domain = _filter_records("tmf.service.test", params)
        recs = request.env["tmf.service.test"].sudo().search(domain)
        fields_param = params.get("fields")
        return _json_response([_apply_fields(r.to_tmf_json(), fields_param) for r in recs], status=200)

    @http.route(f"{SERVICE_TEST_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_service_test(self, rid, **params):
        rec = request.env["tmf.service.test"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"ServiceTest '{rid}' not found")
        return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(SERVICE_TEST_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_service_test(self, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        # Mandatory attributes (TMF653): name, relatedService, testSpecification
        missing = [k for k in ("name", "relatedService", "testSpecification") if not data.get(k)]
        if missing:
            return _error(400, f"Missing mandatory attribute(s): {', '.join(missing)}")

        try:
            rec = request.env["tmf.service.test"].sudo().create_from_tmf(data, base_url=request.httprequest.host_url.rstrip("/"))
            return _json_response(rec.to_tmf_json(), status=201)
        except Exception as e:
            return _error(400, str(e))

    @http.route(f"{SERVICE_TEST_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_service_test(self, rid, **params):
        rec = request.env["tmf.service.test"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"ServiceTest '{rid}' not found")

        ctype = (request.httprequest.content_type or "").lower()
        if "application/merge-patch+json" not in ctype and "application/json-patch+json" not in ctype:
            return _error(415, "Unsupported Content-Type. Use application/merge-patch+json (mandatory)")

        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        try:
            rec.write_from_tmf(data)
            return _json_response(rec.to_tmf_json(), status=200)
        except Exception as e:
            return _error(400, str(e))

    @http.route(f"{SERVICE_TEST_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_service_test(self, rid, **params):
        rec = request.env["tmf.service.test"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"ServiceTest '{rid}' not found")
        rec.unlink()
        return _json_response(None, status=204)

    # ==========================
    # ServiceTestSpecification
    # ==========================
    @http.route(SERVICE_TEST_SPEC_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_service_test_spec(self, **params):
        domain = _filter_records("tmf.service.test.specification", params)
        recs = request.env["tmf.service.test.specification"].sudo().search(domain)
        fields_param = params.get("fields")
        return _json_response([_apply_fields(r.to_tmf_json(), fields_param) for r in recs], status=200)

    @http.route(f"{SERVICE_TEST_SPEC_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_service_test_spec(self, rid, **params):
        rec = request.env["tmf.service.test.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"ServiceTestSpecification '{rid}' not found")
        return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(SERVICE_TEST_SPEC_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_service_test_spec(self, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        # Mandatory attributes (TMF653): name, relatedServiceSpecification
        missing = [k for k in ("name", "relatedServiceSpecification") if not data.get(k)]
        if missing:
            return _error(400, f"Missing mandatory attribute(s): {', '.join(missing)}")

        try:
            rec = request.env["tmf.service.test.specification"].sudo().create_from_tmf(
                data, base_url=request.httprequest.host_url.rstrip("/")
            )
            return _json_response(rec.to_tmf_json(), status=201)
        except Exception as e:
            return _error(400, str(e))

    @http.route(f"{SERVICE_TEST_SPEC_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_service_test_spec(self, rid, **params):
        rec = request.env["tmf.service.test.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"ServiceTestSpecification '{rid}' not found")

        ctype = (request.httprequest.content_type or "").lower()
        if "application/merge-patch+json" not in ctype and "application/json-patch+json" not in ctype:
            return _error(415, "Unsupported Content-Type. Use application/merge-patch+json (mandatory)")

        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        try:
            rec.write_from_tmf(data)
            return _json_response(rec.to_tmf_json(), status=200)
        except Exception as e:
            return _error(400, str(e))

    @http.route(f"{SERVICE_TEST_SPEC_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_service_test_spec(self, rid, **params):
        rec = request.env["tmf.service.test.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"ServiceTestSpecification '{rid}' not found")
        rec.unlink()
        return _json_response(None, status=204)
