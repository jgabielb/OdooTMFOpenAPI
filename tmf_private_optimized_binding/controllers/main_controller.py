# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/privateOptimizedBinding/v5"

RESOURCES = {
    "cloudApplication": {
        "model": "tmf.cloud.application",
        "path": f"{API_BASE}/cloudApplication",
        "required": [],
    },
    "cloudApplicationSpecification": {
        "model": "tmf.cloud.application.specification",
        "path": f"{API_BASE}/cloudApplicationSpecification",
        "required": [],
    },
    "userEquipment": {
        "model": "tmf.user.equipment",
        "path": f"{API_BASE}/userEquipment",
        "required": [],
    },
    "userEquipmentSpecification": {
        "model": "tmf.user.equipment.specification",
        "path": f"{API_BASE}/userEquipmentSpecification",
        "required": [],
    },
}


class TMFPrivateOptimizedBindingController(TMFBaseController):

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
            "name": f"tmf_private_optimized_binding-{callback}",
            "api_name": "cloudApplication",
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
        [RESOURCES["cloudApplication"]["path"], RESOURCES["cloudApplication"]["path"].replace("cloudApplication", "CloudApplication")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def cloudApplication_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["cloudApplication"])
        return self._tmf_do_list(RESOURCES["cloudApplication"], **kw)

    @http.route(
        [RESOURCES["cloudApplication"]["path"] + "/<string:rid>",
         RESOURCES["cloudApplication"]["path"].replace("cloudApplication", "CloudApplication") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def cloudApplication_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["cloudApplication"], rid, **kw)
    @http.route(
        [RESOURCES["cloudApplicationSpecification"]["path"], RESOURCES["cloudApplicationSpecification"]["path"].replace("cloudApplicationSpecification", "CloudApplicationSpecification")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def cloudApplicationSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["cloudApplicationSpecification"])
        return self._tmf_do_list(RESOURCES["cloudApplicationSpecification"], **kw)

    @http.route(
        [RESOURCES["cloudApplicationSpecification"]["path"] + "/<string:rid>",
         RESOURCES["cloudApplicationSpecification"]["path"].replace("cloudApplicationSpecification", "CloudApplicationSpecification") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def cloudApplicationSpecification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["cloudApplicationSpecification"], rid, **kw)
    @http.route(
        [RESOURCES["userEquipment"]["path"], RESOURCES["userEquipment"]["path"].replace("userEquipment", "UserEquipment")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def userEquipment_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["userEquipment"])
        return self._tmf_do_list(RESOURCES["userEquipment"], **kw)

    @http.route(
        [RESOURCES["userEquipment"]["path"] + "/<string:rid>",
         RESOURCES["userEquipment"]["path"].replace("userEquipment", "UserEquipment") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def userEquipment_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["userEquipment"], rid, **kw)
    @http.route(
        [RESOURCES["userEquipmentSpecification"]["path"], RESOURCES["userEquipmentSpecification"]["path"].replace("userEquipmentSpecification", "UserEquipmentSpecification")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def userEquipmentSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["userEquipmentSpecification"])
        return self._tmf_do_list(RESOURCES["userEquipmentSpecification"], **kw)

    @http.route(
        [RESOURCES["userEquipmentSpecification"]["path"] + "/<string:rid>",
         RESOURCES["userEquipmentSpecification"]["path"].replace("userEquipmentSpecification", "UserEquipmentSpecification") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def userEquipmentSpecification_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["userEquipmentSpecification"], rid, **kw)

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/listener/CloudApplicationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationSpecificationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationSpecificationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationSpecificationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CloudApplicationSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_CloudApplicationSpecificationDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentSpecificationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentSpecificationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentSpecificationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/UserEquipmentSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_UserEquipmentSpecificationDeleteEvent(self, **_kw):
        return self._listener_ack()
