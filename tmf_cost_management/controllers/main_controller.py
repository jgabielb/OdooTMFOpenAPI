# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/costManagement/v5"

RESOURCES = {
    "actualCost": {
        "model": "tmf.actual.cost",
        "path": f"{API_BASE}/actualCost",
        "required": [],
    },
    "projectedCost": {
        "model": "tmf.projected.cost",
        "path": f"{API_BASE}/projectedCost",
        "required": [],
    },
}


class TMFCostManagementController(TMFBaseController):

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
            "name": f"tmf_cost_management-{callback}",
            "api_name": "actualCost",
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
        [RESOURCES["actualCost"]["path"], RESOURCES["actualCost"]["path"].replace("actualCost", "ActualCost")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def actualCost_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["actualCost"])
        return self._tmf_do_list(RESOURCES["actualCost"], **kw)

    @http.route(
        [RESOURCES["actualCost"]["path"] + "/<string:rid>",
         RESOURCES["actualCost"]["path"].replace("actualCost", "ActualCost") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def actualCost_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["actualCost"], rid, **kw)
    @http.route(
        [RESOURCES["projectedCost"]["path"], RESOURCES["projectedCost"]["path"].replace("projectedCost", "ProjectedCost")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def projectedCost_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["projectedCost"])
        return self._tmf_do_list(RESOURCES["projectedCost"], **kw)

    @http.route(
        [RESOURCES["projectedCost"]["path"] + "/<string:rid>",
         RESOURCES["projectedCost"]["path"].replace("projectedCost", "ProjectedCost") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def projectedCost_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["projectedCost"], rid, **kw)

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/listener/ActualCostCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ActualCostCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ActualCostAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ActualCostAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ActualCostStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ActualCostStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ActualCostDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ActualCostDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProjectedCostCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ProjectedCostCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProjectedCostAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ProjectedCostAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProjectedCostStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ProjectedCostStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ProjectedCostDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_ProjectedCostDeleteEvent(self, **_kw):
        return self._listener_ack()
