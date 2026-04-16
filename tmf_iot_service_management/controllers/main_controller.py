# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/iotservicemanagement/v4"

RESOURCES = {
    "iotService": {"model": "tmf.iot.service.resource", "path": f"{API_BASE}/iotService", "resource_type": "iotService", "required": []},
    "iotServiceSpecification": {"model": "tmf.iot.service.resource", "path": f"{API_BASE}/iotServiceSpecification", "resource_type": "iotServiceSpecification", "required": []},
}


class TMFIotServiceManagementController(TMFBaseController):




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
            "name": f"tmf_iot_service_management-{callback}",
            "api_name": "iotService",
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
        [RESOURCES["iotService"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def iotService_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["iotService"])
        return self._tmf_do_list(RESOURCES["iotService"], **kw)

    @http.route(
        [RESOURCES["iotService"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def iotService_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["iotService"], rid, **kw)
    @http.route(
        [RESOURCES["iotServiceSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def iotServiceSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["iotServiceSpecification"])
        return self._tmf_do_list(RESOURCES["iotServiceSpecification"], **kw)

    @http.route(
        [RESOURCES["iotServiceSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def iotServiceSpecification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["iotServiceSpecification"], rid, **kw)

    @http.route(f"{API_BASE}/listener/IotServiceCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicecreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotserviceattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicestatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicedeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicespecificationcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicespecificationattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicespecificationstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/IotServiceSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_iotservicespecificationdeleteevent(self, **_kw):
        return self._listener_ack()
