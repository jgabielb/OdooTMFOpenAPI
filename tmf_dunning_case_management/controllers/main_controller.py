# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/dunningCase/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "dunningScenario": {
        "model": "tmf.dunning.scenario",
        "path": f"{API_BASE}/dunningScenario",
        "required": [],
    },
    "dunningRule": {
        "model": "tmf.dunning.rule",
        "path": f"{API_BASE}/dunningRule",
        "required": [],
    },
    "dunningCase": {
        "model": "tmf.dunning.case",
        "path": f"{API_BASE}/dunningCase",
        "required": [],
    },
}


class TMFDunningCaseManagementController(TMFBaseController):

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
            "name": f"tmf_dunning_case_management-{callback}",
            "api_name": "dunningScenario",
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
        [RESOURCES["dunningScenario"]["path"], RESOURCES["dunningScenario"]["path"].replace("dunningScenario", "DunningScenario")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def dunningScenario_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("dunningScenario")
        return self._tmf_list("dunningScenario", **kw)

    @http.route(
        [RESOURCES["dunningScenario"]["path"] + "/<string:rid>",
         RESOURCES["dunningScenario"]["path"].replace("dunningScenario", "DunningScenario") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def dunningScenario_individual(self, rid, **kw):
        return self._tmf_individual("dunningScenario", rid, **kw)
    @http.route(
        [RESOURCES["dunningRule"]["path"], RESOURCES["dunningRule"]["path"].replace("dunningRule", "DunningRule")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def dunningRule_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("dunningRule")
        return self._tmf_list("dunningRule", **kw)

    @http.route(
        [RESOURCES["dunningRule"]["path"] + "/<string:rid>",
         RESOURCES["dunningRule"]["path"].replace("dunningRule", "DunningRule") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def dunningRule_individual(self, rid, **kw):
        return self._tmf_individual("dunningRule", rid, **kw)
    @http.route(
        [RESOURCES["dunningCase"]["path"], RESOURCES["dunningCase"]["path"].replace("dunningCase", "DunningCase")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def dunningCase_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("dunningCase")
        return self._tmf_list("dunningCase", **kw)

    @http.route(
        [RESOURCES["dunningCase"]["path"] + "/<string:rid>",
         RESOURCES["dunningCase"]["path"].replace("dunningCase", "DunningCase") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def dunningCase_individual(self, rid, **kw):
        return self._tmf_individual("dunningCase", rid, **kw)

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/listener/DunningCaseCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningCaseCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningCaseAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningCaseAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningCaseStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningCaseStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningCaseDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningCaseDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningRuleCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningRuleCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningRuleAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningRuleAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningRuleStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningRuleStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningRuleDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningRuleDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningScenarioCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningScenarioCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningScenarioAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningScenarioAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningScenarioStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningScenarioStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/DunningScenarioDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_DunningScenarioDeleteEvent(self, **_kw):
        return self._listener_ack()
