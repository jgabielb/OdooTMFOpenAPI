# -*- coding: utf-8 -*-
"""TMF649 Performance Threshold Management API.

Threshold / ThresholdJob are stored as ``tmf.performance.management.resource``
records discriminated by ``resource_type``, giving TMFC037/TMFC038 their
YAML-exposed TMF649 surface.
"""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/thresholdManagement/v4"

RESOURCES = {
    "threshold": {
        "model": "tmf.performance.management.resource",
        "path": f"{API_BASE}/threshold",
        "resource_type": "threshold",
        "required": [],
    },
    "thresholdJob": {
        "model": "tmf.performance.management.resource",
        "path": f"{API_BASE}/thresholdJob",
        "resource_type": "thresholdJob",
        "required": [],
    },
}


class TMF649ThresholdController(TMFBaseController):

    def _threshold_to_json(self, rec):
        payload = rec.to_tmf_json()
        payload["href"] = (request.httprequest.host_url.rstrip("/")
                           + f"{API_BASE}/{rec.resource_type}/{rec.tmf_id or rec.id}")
        return payload

    def _collection(self, res_key, **kw):
        cfg = RESOURCES[res_key]
        if request.httprequest.method == "POST":
            return self._tmf_do_create(cfg)
        domain = [("resource_type", "=", cfg["resource_type"])]
        return self._list_response(cfg["model"], domain, self._threshold_to_json, kw)

    def _individual(self, res_key, rid, **kw):
        cfg = RESOURCES[res_key]
        Model = request.env[cfg["model"]].sudo()
        rec = Model.search([("tmf_id", "=", str(rid)),
                            ("resource_type", "=", cfg["resource_type"])], limit=1)
        if not rec and str(rid).isdigit():
            candidate = Model.browse(int(rid))
            if candidate.exists() and candidate.resource_type == cfg["resource_type"]:
                rec = candidate
        if not rec:
            return self._error(404, "Not Found", f"{res_key} {rid} not found")
        method = request.httprequest.method
        if method == "PATCH":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            data.pop("id", None)
            data.pop("href", None)
            vals = Model.from_tmf_json(data, partial=True)
            if vals:
                rec.write(vals)
            return self._json(self._threshold_to_json(rec))
        if method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json(self._select_fields(self._threshold_to_json(rec), kw.get("fields")))

    @http.route(RESOURCES["threshold"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def threshold_collection(self, **kw):
        return self._collection("threshold", **kw)

    @http.route(RESOURCES["threshold"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def threshold_individual(self, rid, **kw):
        return self._individual("threshold", rid, **kw)

    @http.route(RESOURCES["thresholdJob"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def threshold_job_collection(self, **kw):
        return self._collection("thresholdJob", **kw)

    @http.route(RESOURCES["thresholdJob"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def threshold_job_individual(self, rid, **kw):
        return self._individual("thresholdJob", rid, **kw)

    @http.route(f"{API_BASE}/hub", type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("name", "like", "tmf649-")])
            return self._json([{"id": str(s.id), "callback": s.callback,
                                "query": s.query or ""} for s in subs])
        data = self._parse_json_body()
        callback = (data or {}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        api_name = (data or {}).get("api_name") or "threshold"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf649-{api_name}-{callback}",
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
        if not rec.exists() or not rec.name.startswith("tmf649-"):
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""})
