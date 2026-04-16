# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/processFlowManagement/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "processFlow": {"model": "tmf.process.flow", "path": f"{API_BASE}/processFlow", "required": []},
    "taskFlow": {"model": "tmf.task.flow", "path": f"{API_BASE}/taskFlow", "required": []},
    "processFlowSpecification": {"model": "tmf.process.flow.specification", "path": f"{API_BASE}/processFlowSpecification", "required": ["name"]},
    "taskFlowSpecification": {"model": "tmf.task.flow.specification", "path": f"{API_BASE}/taskFlowSpecification", "required": ["name"]},
}


class TMFProcessFlowController(TMFBaseController):

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
            return self._tmf_create("processFlow")
        return self._tmf_list("processFlow", **kw)

    @http.route(
        [RESOURCES["processFlow"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def processFlow_individual(self, rid, **kw):
        return self._tmf_individual("processFlow", rid, **kw)
    @http.route(
        [RESOURCES["taskFlow"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def taskFlow_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("taskFlow")
        return self._tmf_list("taskFlow", **kw)

    @http.route(
        [RESOURCES["taskFlow"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def taskFlow_individual(self, rid, **kw):
        return self._tmf_individual("taskFlow", rid, **kw)
    @http.route(
        [RESOURCES["processFlowSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def processFlowSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("processFlowSpecification")
        return self._tmf_list("processFlowSpecification", **kw)

    @http.route(
        [RESOURCES["processFlowSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def processFlowSpecification_individual(self, rid, **kw):
        return self._tmf_individual("processFlowSpecification", rid, **kw)
    @http.route(
        [RESOURCES["taskFlowSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def taskFlowSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("taskFlowSpecification")
        return self._tmf_list("taskFlowSpecification", **kw)

    @http.route(
        [RESOURCES["taskFlowSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def taskFlowSpecification_individual(self, rid, **kw):
        return self._tmf_individual("taskFlowSpecification", rid, **kw)

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
