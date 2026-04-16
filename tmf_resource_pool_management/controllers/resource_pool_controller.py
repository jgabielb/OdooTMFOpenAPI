# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/resourcePoolManagement/v5"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "resourcePool": {"model": "tmf.resource.pool", "path": f"{API_BASE}/resourcePool", "required": []},
    "resourcePoolSpecification": {"model": "tmf.resource.pool.specification", "path": f"{API_BASE}/resourcePoolSpecification", "required": ["name"]},
    "capacitySpecification": {"model": "tmf.capacity.specification", "path": f"{API_BASE}/capacitySpecification", "required": ["name"]},
    "availabilityCheck": {"model": "tmf.resource.pool.availability.check", "path": f"{API_BASE}/availabilityCheck", "required": []},
    "push": {"model": "tmf.resource.pool.push", "path": f"{API_BASE}/push", "required": []},
    "extract": {"model": "tmf.resource.pool.extract", "path": f"{API_BASE}/extract", "required": []},
}


class TMFResourcePoolManagementController(TMFBaseController):

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
            "name": f"tmf_resource_pool_management-{callback}",
            "api_name": "resourcePool",
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
        [RESOURCES["resourcePool"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def resourcePool_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("resourcePool")
        return self._tmf_list("resourcePool", **kw)

    @http.route(
        [RESOURCES["resourcePool"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def resourcePool_individual(self, rid, **kw):
        return self._tmf_individual("resourcePool", rid, **kw)
    @http.route(
        [RESOURCES["resourcePoolSpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def resourcePoolSpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("resourcePoolSpecification")
        return self._tmf_list("resourcePoolSpecification", **kw)

    @http.route(
        [RESOURCES["resourcePoolSpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def resourcePoolSpecification_individual(self, rid, **kw):
        return self._tmf_individual("resourcePoolSpecification", rid, **kw)
    @http.route(
        [RESOURCES["capacitySpecification"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def capacitySpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("capacitySpecification")
        return self._tmf_list("capacitySpecification", **kw)

    @http.route(
        [RESOURCES["capacitySpecification"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def capacitySpecification_individual(self, rid, **kw):
        return self._tmf_individual("capacitySpecification", rid, **kw)
    @http.route(
        [RESOURCES["availabilityCheck"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def availabilityCheck_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("availabilityCheck")
        return self._tmf_list("availabilityCheck", **kw)

    @http.route(
        [RESOURCES["availabilityCheck"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def availabilityCheck_individual(self, rid, **kw):
        return self._tmf_individual("availabilityCheck", rid, **kw)
    @http.route(
        [RESOURCES["push"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def push_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("push")
        return self._tmf_list("push", **kw)

    @http.route(
        [RESOURCES["push"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def push_individual(self, rid, **kw):
        return self._tmf_individual("push", rid, **kw)
    @http.route(
        [RESOURCES["extract"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def extract_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("extract")
        return self._tmf_list("extract", **kw)

    @http.route(
        [RESOURCES["extract"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def extract_individual(self, rid, **kw):
        return self._tmf_individual("extract", rid, **kw)

    @http.route(f"{API_BASE}/listener/ResourcePoolCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepooldeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolspecificationcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolspecificationattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolspecificationstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/ResourcePoolSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resourcepoolspecificationdeleteevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CapacitySpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_capacityspecificationcreateevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CapacitySpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_capacityspecificationattributevaluechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CapacitySpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_capacityspecificationstatechangeevent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/CapacitySpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_capacityspecificationdeleteevent(self, **_kw):
        return self._listener_ack()
