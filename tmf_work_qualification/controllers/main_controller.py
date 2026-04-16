# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/workQualificationManagement/v4"

RESOURCES = {
    "checkWorkQualification": {
        "model": "tmf.check.work.qualification",
        "path": f"{API_BASE}/checkWorkQualification",
        "required": [],
    },
    "queryWorkQualification": {
        "model": "tmf.query.work.qualification",
        "path": f"{API_BASE}/queryWorkQualification",
        "required": [],
    },
}


class TMFWorkQualificationController(TMFBaseController):

    # ------------------------------------------------------------------
    # Generic CRUD using TMFBaseController helpers
    # ------------------------------------------------------------------

    def _tmf_list(self, res_key, **kw):
        cfg = RESOURCES[res_key]
        model = cfg["model"]
        domain = []
        for key, val in kw.items():
            if key in ("fields", "offset", "limit", "sort"):
                continue
            if val and hasattr(request.env[model], key):
                domain.append((key, "=", val))
        return self._list_response(model, domain, lambda r: r.to_tmf_json(), kw)



    # ------------------------------------------------------------------
    # Hub
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("callback", "!=", False)])
            return self._json([{"id": str(s.id), "callback": s.callback, "query": s.query or ""} for s in subs])
        data = self._parse_json_body()
        callback = (data or {}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf_work_qualification-{callback}",
            "api_name": "checkWorkQualification",
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

    # ------------------------------------------------------------------
    # Listener (acknowledge only)
    # ------------------------------------------------------------------

    def _listener_ack(self):
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid event payload")
        return request.make_response("", status=201)

    # ------------------------------------------------------------------
    # Resource routes
    # ------------------------------------------------------------------

    @http.route(
        [RESOURCES["checkWorkQualification"]["path"], RESOURCES["checkWorkQualification"]["path"].replace("checkWorkQualification", "CheckWorkQualification")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def checkWorkQualification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["checkWorkQualification"])
        return self._tmf_do_list(RESOURCES["checkWorkQualification"], **kw)

    @http.route(
        [RESOURCES["checkWorkQualification"]["path"] + "/<string:rid>",
         RESOURCES["checkWorkQualification"]["path"].replace("checkWorkQualification", "CheckWorkQualification") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def checkWorkQualification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["checkWorkQualification"], rid, **kw)
    @http.route(
        [RESOURCES["queryWorkQualification"]["path"], RESOURCES["queryWorkQualification"]["path"].replace("queryWorkQualification", "QueryWorkQualification")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def queryWorkQualification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["queryWorkQualification"])
        return self._tmf_do_list(RESOURCES["queryWorkQualification"], **kw)

    @http.route(
        [RESOURCES["queryWorkQualification"]["path"] + "/<string:rid>",
         RESOURCES["queryWorkQualification"]["path"].replace("queryWorkQualification", "QueryWorkQualification") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def queryWorkQualification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["queryWorkQualification"], rid, **kw)

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/listener/CheckWorkQualificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CheckWorkQualificationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CheckWorkQualificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CheckWorkQualificationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CheckWorkQualificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CheckWorkQualificationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CheckWorkQualificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CheckWorkQualificationDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/QueryWorkQualificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_QueryWorkQualificationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/QueryWorkQualificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_QueryWorkQualificationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/QueryWorkQualificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_QueryWorkQualificationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/QueryWorkQualificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_QueryWorkQualificationDeleteEvent(self, **_kw):
        return self._listener_ack()
