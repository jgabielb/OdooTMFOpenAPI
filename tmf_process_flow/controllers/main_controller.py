# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/processFlowManagement/v4"

RESOURCES = {
    "processFlow": {"model": "tmf.process.flow", "path": f"{API_BASE}/processFlow", "required": []},
    "taskFlow": {"model": "tmf.task.flow", "path": f"{API_BASE}/taskFlow", "required": []},
    "processFlowSpecification": {"model": "tmf.process.flow.specification", "path": f"{API_BASE}/processFlowSpecification", "required": ["name"]},
    "taskFlowSpecification": {"model": "tmf.task.flow.specification", "path": f"{API_BASE}/taskFlowSpecification", "required": ["name"]},
}


class TMFProcessFlowController(TMFBaseController):




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
            "name": f"tmf_process_flow-{callback}",
            "api_name": "processFlow",
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
        [RESOURCES["processFlow"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def processFlow_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["processFlow"])
        return self._tmf_do_list(RESOURCES["processFlow"], **kw)

    @http.route(
        [RESOURCES["processFlow"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def processFlow_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["processFlow"], rid, **kw)
    @http.route(
        [RESOURCES["taskFlow"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def taskFlow_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["taskFlow"])
        return self._tmf_do_list(RESOURCES["taskFlow"], **kw)

    @http.route(
        [RESOURCES["taskFlow"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def taskFlow_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["taskFlow"], rid, **kw)
    @http.route(
        [RESOURCES["processFlowSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def processFlowSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["processFlowSpecification"])
        return self._tmf_do_list(RESOURCES["processFlowSpecification"], **kw)

    @http.route(
        [RESOURCES["processFlowSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def processFlowSpecification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["processFlowSpecification"], rid, **kw)
    @http.route(
        [RESOURCES["taskFlowSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def taskFlowSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["taskFlowSpecification"])
        return self._tmf_do_list(RESOURCES["taskFlowSpecification"], **kw)

    @http.route(
        [RESOURCES["taskFlowSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def taskFlowSpecification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["taskFlowSpecification"], rid, **kw)

    @http.route(f"{API_BASE}/listener/ProcessFlowCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowspecificationcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowspecificationattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowspecificationstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProcessFlowSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_processflowspecificationdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowspecificationcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowspecificationattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowspecificationstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/TaskFlowSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_taskflowspecificationdeleteevent(self, **_kw):
        return self._listener_ack()
