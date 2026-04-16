# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/tmf-componentsuite/selfcareapp/v1"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "selfCareApp": {"model": "tmf.self.care.resource", "path": f"{API_BASE}/selfCareApp", "required": []},
    "selfCareAppSpecification": {"model": "tmf.self.care.resource", "path": f"{API_BASE}/selfCareAppSpecification", "required": []},
}


class TMFSelfCareManagementController(TMFBaseController):

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
            "name": f"tmf_self_care_management-{callback}",
            "api_name": "selfCareApp",
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
        [RESOURCES["selfCareApp"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def selfCareApp_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("selfCareApp")
        return self._tmf_list("selfCareApp", **kw)

    @http.route(
        [RESOURCES["selfCareApp"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def selfCareApp_individual(self, rid, **kw):
        return self._tmf_individual("selfCareApp", rid, **kw)
    @http.route(
        [RESOURCES["selfCareAppSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def selfCareAppSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("selfCareAppSpecification")
        return self._tmf_list("selfCareAppSpecification", **kw)

    @http.route(
        [RESOURCES["selfCareAppSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def selfCareAppSpecification_individual(self, rid, **kw):
        return self._tmf_individual("selfCareAppSpecification", rid, **kw)

    @http.route(f"{API_BASE}/listener/SelfCareAppCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappspecificationcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappspecificationattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappspecificationstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/SelfCareAppSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_selfcareappspecificationdeleteevent(self, **_kw):
        return self._listener_ack()
