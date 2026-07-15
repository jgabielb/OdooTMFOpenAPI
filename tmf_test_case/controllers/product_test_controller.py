# -*- coding: utf-8 -*-
"""TMF769 Product Test Management API (productTest, productTestSpecification)."""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/productTestManagement/v4"

RESOURCES = {
    "productTest": {
        "model": "tmf.product.test",
        "path": f"{API_BASE}/productTest",
        "required": [],
    },
    "productTestSpecification": {
        "model": "tmf.product.test.specification",
        "path": f"{API_BASE}/productTestSpecification",
        "required": [],
    },
}


class TMF769ProductTestController(TMFBaseController):

    @http.route(RESOURCES["productTest"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def product_test_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["productTest"])
        return self._tmf_do_list(RESOURCES["productTest"], **kw)

    @http.route(RESOURCES["productTest"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def product_test_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["productTest"], rid, **kw)

    @http.route(RESOURCES["productTestSpecification"]["path"], type="http",
                auth="public", methods=["GET", "POST"], csrf=False)
    def product_test_spec_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["productTestSpecification"])
        return self._tmf_do_list(RESOURCES["productTestSpecification"], **kw)

    @http.route(RESOURCES["productTestSpecification"]["path"] + "/<string:rid>",
                type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def product_test_spec_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["productTestSpecification"], rid, **kw)

    @http.route(f"{API_BASE}/hub", type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("name", "like", "tmf769-")])
            return self._json([{"id": str(s.id), "callback": s.callback,
                                "query": s.query or ""} for s in subs])
        data = self._parse_json_body()
        callback = (data or {}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        api_name = (data or {}).get("api_name") or "productTest"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf769-{api_name}-{callback}",
            "api_name": api_name,
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("eventType") or "any",
            "content_type": "application/json",
        })
        return self._json({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""}, status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public",
                methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_kw):
        if not str(sid).isdigit():
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
        if not rec.exists() or not rec.name.startswith("tmf769-"):
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""})
