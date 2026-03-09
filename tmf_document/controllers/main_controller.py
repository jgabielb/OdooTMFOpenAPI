# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

API_BASE = "/tmf-api/document/v4"
RESOURCE = "document"
BASE_PATH = f"{API_BASE}/{RESOURCE}"


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


def _fields_param(params):
    # TMF supports attribute selection on first-level attributes (fields=...)
    fields_raw = (params.get("fields") or "").strip()
    if not fields_raw:
        return None
    return [f.strip() for f in fields_raw.split(",") if f.strip()]


class TMF667DocumentController(http.Controller):

    # List documents: GET /document?fields=...&{filtering}
    @http.route(BASE_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_documents(self, **params):
        domain = []

        # Minimal filtering support (common TMF pattern):
        # documentType=..., status=..., name=...
        # (Spec says filtering may be available depending on compliance level.)
        if params.get("documentType"):
            domain.append(("document_type", "=", params["documentType"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))

        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0

        env = request.env["tmf.document"].sudo()
        records = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)

        wanted = _fields_param(params)
        payload = [r.to_tmf_json(fields=wanted) for r in records]
        return _json_response(payload, status=200, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(payload))),
        ])

    # Retrieve document: GET /document/{id}?fields=...
    @http.route(f"{BASE_PATH}/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_document(self, tmf_id, **params):
        rec = request.env["tmf.document"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, f"Document {tmf_id} not found")

        wanted = _fields_param(params)
        return _json_response(rec.to_tmf_json(fields=wanted), status=200)

    # Create document: POST /document (Mandatory: name)
    @http.route(BASE_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_document(self, **_params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        name = (data.get("name") or "").strip()
        if not name:
            return _error(400, "Missing mandatory attribute: name")

        try:
            vals = request.env["tmf.document"].sudo().from_tmf_json(data)
            rec = request.env["tmf.document"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)
        except Exception as e:
            return _error(400, "Create failed", details=str(e))

    # Patch document: PATCH /document/{id} (merge-patch mandatory)
    @http.route(f"{BASE_PATH}/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_document(self, tmf_id, **_params):
        rec = request.env["tmf.document"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, f"Document {tmf_id} not found")

        # Enforce JSON Merge Patch if provided
        ctype = (request.httprequest.content_type or "").lower()
        if ctype and "application/merge-patch+json" not in ctype and "application/json" not in ctype:
            return _error(415, "Unsupported Media Type. Use application/merge-patch+json")

        patch = _parse_json_body()
        if patch is None:
            return _error(400, "Invalid JSON body")

        # Non-patchable: id, href
        if "id" in patch or "href" in patch:
            return _error(400, "Non patchable attributes present: id/href")

        try:
            vals = request.env["tmf.document"].sudo().from_tmf_json(patch, partial=True)
            rec.write(vals)
            return _json_response(rec.to_tmf_json(), status=200)
        except Exception as e:
            return _error(400, "Patch failed", details=str(e))

    # Delete document: DELETE /document/{id}
    @http.route(f"{BASE_PATH}/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_document(self, tmf_id, **_params):
        rec = request.env["tmf.document"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            # TMF implementations vary; 404 is acceptable.
            return _error(404, f"Document {tmf_id} not found")

        try:
            rec.unlink()
            return request.make_response("", status=204)
        except Exception as e:
            return _error(400, "Delete failed", details=str(e))
