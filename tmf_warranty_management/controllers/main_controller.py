# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/warrantyManagement/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "warranty": {
        "model": "tmf.warranty",
        "path": f"{API_BASE}/warranty",
        "required": [],
    },
    "warrantySpecification": {
        "model": "tmf.warranty.specification",
        "path": f"{API_BASE}/warrantySpecification",
        "required": [],
    },
}


class TMFWarrantyManagementController(TMFBaseController):

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
            "name": f"tmf_warranty_management-{callback}",
            "api_name": "warranty",
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
        [RESOURCES["warranty"]["path"], RESOURCES["warranty"]["path"].replace("warranty", "Warranty")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def warranty_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("warranty")
        return self._tmf_list("warranty", **kw)

    @http.route(
        [RESOURCES["warranty"]["path"] + "/<string:rid>",
         RESOURCES["warranty"]["path"].replace("warranty", "Warranty") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def warranty_individual(self, rid, **kw):
        return self._tmf_individual("warranty", rid, **kw)
    @http.route(
        [RESOURCES["warrantySpecification"]["path"], RESOURCES["warrantySpecification"]["path"].replace("warrantySpecification", "WarrantySpecification")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def warrantySpecification_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("warrantySpecification")
        return self._tmf_list("warrantySpecification", **kw)

    @http.route(
        [RESOURCES["warrantySpecification"]["path"] + "/<string:rid>",
         RESOURCES["warrantySpecification"]["path"].replace("warrantySpecification", "WarrantySpecification") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def warrantySpecification_individual(self, rid, **kw):
        return self._tmf_individual("warrantySpecification", rid, **kw)

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/listener/WarrantyCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantyCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantyAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantyAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantyStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantyStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantyDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantyDeleteEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantySpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantySpecificationCreateEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantySpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantySpecificationAttributeValueChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantySpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantySpecificationStateChangeEvent(self, **_kw):
        return self._listener_ack()
    @http.route(f"{API_BASE}/listener/WarrantySpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_WarrantySpecificationDeleteEvent(self, **_kw):
        return self._listener_ack()
