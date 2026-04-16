# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/workManagement/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "work": {
        "model": "tmf.work",
        "path": f"{API_BASE}/work",
        "required": [],
    },
    "workSpecification": {
        "model": "tmf.work.specification",
        "path": f"{API_BASE}/workSpecification",
        "required": [],
    },
}


class TMFWorkManagementController(TMFBaseController):

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
            "name": f"tmf_work_management-{callback}",
            "api_name": "work",
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
        [RESOURCES["work"]["path"], RESOURCES["work"]["path"].replace("work", "Work")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def work_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("work")
        return self._tmf_list("work", **kw)

    @http.route(
        [RESOURCES["work"]["path"] + "/<string:rid>",
         RESOURCES["work"]["path"].replace("work", "Work") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def work_individual(self, rid, **kw):
        return self._tmf_individual("work", rid, **kw)
    @http.route(
        [RESOURCES["workSpecification"]["path"], RESOURCES["workSpecification"]["path"].replace("workSpecification", "WorkSpecification")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def workSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("workSpecification")
        return self._tmf_list("workSpecification", **kw)

    @http.route(
        [RESOURCES["workSpecification"]["path"] + "/<string:rid>",
         RESOURCES["workSpecification"]["path"].replace("workSpecification", "WorkSpecification") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def workSpecification_individual(self, rid, **kw):
        return self._tmf_individual("workSpecification", rid, **kw)

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/listener/WorkCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkSpecificationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkSpecificationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkSpecificationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WorkSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WorkSpecificationDeleteEvent(self, **_kw):
        return self._listener_ack()
