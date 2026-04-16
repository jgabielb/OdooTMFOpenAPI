# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/performance/v5"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "performanceMeasurementJob": {"model": "tmf.performance.management.resource", "path": f"{API_BASE}/performanceMeasurementJob", "required": []},
    "performanceMeasurementCollection": {"model": "tmf.performance.management.resource", "path": f"{API_BASE}/performanceMeasurementCollection", "required": []},
}


class TMFPerformanceManagementController(TMFBaseController):

    def _tmf_list(self, res_key, **kw):
        cfg = RESOURCES[res_key]
        return self._list_response(cfg["model"], [], lambda r: r.to_tmf_json(), kw)

    def _tmf_create(self, res_key):
        cfg = RESOURCES[res_key]
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid JSON body")
        for req in cfg.get("required", []):
            if req not in data:
                return self._error(400, "Bad Request", f"Missing mandatory attribute: {req}")
        Model = request.env[cfg["model"]].sudo()
        if hasattr(Model, "from_tmf_json"):
            vals = Model.from_tmf_json(data)
        else:
            vals = data
        rec = Model.create(vals)
        return self._json(rec.to_tmf_json(), status=201)

    def _tmf_individual(self, res_key, rid, **kw):
        cfg = RESOURCES[res_key]
        rid = self._normalize_tmf_id(rid)
        rec = self._find_record(cfg["model"], rid)
        if not rec:
            return self._error(404, "Not Found", f"{res_key} {rid} not found")
        method = request.httprequest.method
        if method == "GET":
            return self._json(self._select_fields(rec.to_tmf_json(), kw.get("fields")))
        elif method == "PATCH":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            illegal = [k for k in data if k in NON_PATCHABLE]
            if illegal:
                return self._error(400, "Bad Request", f"Non-patchable attribute(s): {', '.join(illegal)}")
            Model = request.env[cfg["model"]].sudo()
            if hasattr(Model, "from_tmf_json"):
                vals = Model.from_tmf_json(data, partial=True)
            else:
                vals = data
            rec.write(vals)
            return self._json(rec.to_tmf_json())
        elif method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._error(405, "Method Not Allowed", f"{method} not supported")

    # Hub
    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("callback", "!=", False)])
            return self._json([{"id": str(s.id), "callback": s.callback, "query": s.query or ""} for s in subs])
        data = self._parse_json_body()
        callback = (data or {}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf_performance_management-{callback}",
            "api_name": "performanceMeasurementJob",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("eventType") or "any",
            "content_type": "application/json",
        })
        return self._json({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}, status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_kw):
        if not str(sid).isdigit():
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
        if not rec.exists():
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""})

    def _listener_ack(self):
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid event payload")
        return request.make_response("", status=201)

    @http.route(
        [RESOURCES["performanceMeasurementJob"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def performanceMeasurementJob_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("performanceMeasurementJob")
        return self._tmf_list("performanceMeasurementJob", **kw)

    @http.route(
        [RESOURCES["performanceMeasurementJob"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def performanceMeasurementJob_individual(self, rid, **kw):
        return self._tmf_individual("performanceMeasurementJob", rid, **kw)
    @http.route(
        [RESOURCES["performanceMeasurementCollection"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def performanceMeasurementCollection_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("performanceMeasurementCollection")
        return self._tmf_list("performanceMeasurementCollection", **kw)

    @http.route(
        [RESOURCES["performanceMeasurementCollection"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def performanceMeasurementCollection_individual(self, rid, **kw):
        return self._tmf_individual("performanceMeasurementCollection", rid, **kw)

    @http.route(f"{API_BASE}/listener/PerformanceMeasurementJobCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementjobcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementJobAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementjobattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementJobStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementjobstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementJobDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementjobdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementCollectionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementcollectioncreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementCollectionAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementcollectionattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementCollectionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementcollectionstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/PerformanceMeasurementCollectionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_performancemeasurementcollectiondeleteevent(self, **_kw):
        return self._listener_ack()
