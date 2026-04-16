# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/naas/v4"

RESOURCES = {
    "naasRequest": {"model": "tmf.naas.resource", "path": f"{API_BASE}/naasRequest", "resource_type": "naasRequest", "required": []},
    "naasTemplate": {"model": "tmf.naas.resource", "path": f"{API_BASE}/naasTemplate", "resource_type": "naasTemplate", "required": []},
}


class TMFNetworkAsAServiceManagementController(TMFBaseController):




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
            "name": f"tmf_network_as_a_service_management-{callback}",
            "api_name": "naasRequest",
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
        [RESOURCES["naasRequest"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def naasRequest_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["naasRequest"])
        return self._tmf_do_list(RESOURCES["naasRequest"], **kw)

    @http.route(
        [RESOURCES["naasRequest"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def naasRequest_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["naasRequest"], rid, **kw)
    @http.route(
        [RESOURCES["naasTemplate"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def naasTemplate_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["naasTemplate"])
        return self._tmf_do_list(RESOURCES["naasTemplate"], **kw)

    @http.route(
        [RESOURCES["naasTemplate"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def naasTemplate_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["naasTemplate"], rid, **kw)

    @http.route(f"{API_BASE}/listener/NaasRequestCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naasrequestcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasRequestAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naasrequestattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasRequestStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naasrequeststatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasRequestDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naasrequestdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasTemplateCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naastemplatecreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasTemplateAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naastemplateattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasTemplateStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naastemplatestatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/NaasTemplateDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_naastemplatedeleteevent(self, **_kw):
        return self._listener_ack()
