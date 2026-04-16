# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/performance/v5"

RESOURCES = {
    "performanceMeasurementJob": {"model": "tmf.performance.management.resource", "path": f"{API_BASE}/performanceMeasurementJob", "resource_type": "performanceMeasurementJob", "required": []},
    "performanceMeasurementCollection": {"model": "tmf.performance.management.resource", "path": f"{API_BASE}/performanceMeasurementCollection", "resource_type": "performanceMeasurementCollection", "required": []},
}


class TMFPerformanceManagementController(TMFBaseController):




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
            return self._tmf_do_create(RESOURCES["performanceMeasurementJob"])
        return self._tmf_do_list(RESOURCES["performanceMeasurementJob"], **kw)

    @http.route(
        [RESOURCES["performanceMeasurementJob"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def performanceMeasurementJob_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["performanceMeasurementJob"], rid, **kw)
    @http.route(
        [RESOURCES["performanceMeasurementCollection"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def performanceMeasurementCollection_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["performanceMeasurementCollection"])
        return self._tmf_do_list(RESOURCES["performanceMeasurementCollection"], **kw)

    @http.route(
        [RESOURCES["performanceMeasurementCollection"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def performanceMeasurementCollection_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["performanceMeasurementCollection"], rid, **kw)

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
