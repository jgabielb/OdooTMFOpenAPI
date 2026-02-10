# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request
from .common import API_BASE, _json_response, _error, _parse_json_body, _new_id

# Per TMF guideline in the doc: POST /hub, DELETE /hub/{id} :contentReference[oaicite:10]{index=10}
BASE_PATH = f"{API_BASE}/hub"


class TMF657HubController(http.Controller):

    @http.route(f"{BASE_PATH}", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **kwargs):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="INVALID_JSON", details=str(e))

        callback = body.get("callback")
        if not callback:
            return _error(400, "Bad Request", code="MISSING_MANDATORY", details={"missing": ["callback"]})

        rec_id = _new_id()
        vals = {
            "tmf_id": rec_id,
            "callback": callback,
            "query": body.get("query"),
            "headers_json": json.dumps(body.get("headers")) if body.get("headers") is not None else False,
        }

        rec = request.env["tmf657.hub.subscription"].sudo().create(vals)
        return _json_response(rec.to_tmf_dict(base_path=BASE_PATH), status=201)

    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, rid, **kwargs):
        env = request.env["tmf657.hub.subscription"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="NOT_FOUND", details=f"hub {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)
