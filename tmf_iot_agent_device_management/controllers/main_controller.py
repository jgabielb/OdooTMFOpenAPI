# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/iotdevicemanagement/v4"

RESOURCES = {
    "device": {"model": "tmf.iot.agent.device.resource", "path": f"{API_BASE}/device", "required": []},
    "agent": {"model": "tmf.iot.agent.device.resource", "path": f"{API_BASE}/agent", "required": []},
}


class TMFIotAgentDeviceManagementController(TMFBaseController):




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
            "name": f"tmf_iot_agent_device_management-{callback}",
            "api_name": "device",
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
        [RESOURCES["device"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def device_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["device"])
        return self._tmf_do_list(RESOURCES["device"], **kw)

    @http.route(
        [RESOURCES["device"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def device_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["device"], rid, **kw)
    @http.route(
        [RESOURCES["agent"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def agent_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["agent"])
        return self._tmf_do_list(RESOURCES["agent"], **kw)

    @http.route(
        [RESOURCES["agent"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def agent_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["agent"], rid, **kw)

    @http.route(f"{API_BASE}/listener/DeviceCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_devicecreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DeviceAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_deviceattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DeviceStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_devicestatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DeviceDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_devicedeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/AgentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_agentcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/AgentAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_agentattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/AgentStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_agentstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/AgentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_agentdeleteevent(self, **_kw):
        return self._listener_ack()
