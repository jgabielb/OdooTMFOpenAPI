# -*- coding: utf-8 -*-
"""TMF697 Work Order Management API.

WorkOrder is represented locally by ``tmf.work`` records typed
``@type = WorkOrder`` (CancelWorkOrder tasks as ``@type = CancelWorkOrder``),
so ODA components (TMFC061 exposed, TMFC007 dependent) get a real TMF697
surface without a parallel model.
"""
import json
import logging
import uuid

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/workOrderingManagement/v4"
WORK_ORDER_TYPE = "WorkOrder"
CANCEL_TYPE = "CancelWorkOrder"


class TMF697WorkOrderController(TMFBaseController):

    def _wo_base_url(self):
        return request.httprequest.host_url.rstrip("/") + API_BASE

    def _wo_to_json(self, rec):
        payload = rec.to_tmf_json()
        path = "workOrder" if (rec.tmf_type_value or "") == WORK_ORDER_TYPE else "cancelWorkOrder"
        payload["href"] = f"{self._wo_base_url()}/{path}/{rec.tmf_id or rec.id}"
        return payload

    def _wo_find(self, rid, tmf_type):
        Model = request.env["tmf.work"].sudo()
        rec = Model.search([("tmf_id", "=", str(rid)), ("tmf_type_value", "=", tmf_type)],
                           limit=1)
        if not rec and str(rid).isdigit():
            candidate = Model.browse(int(rid))
            if candidate.exists() and (candidate.tmf_type_value or "") == tmf_type:
                rec = candidate
        return rec

    # ------------------------------------------------------------------
    # workOrder
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/workOrder", type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def work_order_collection(self, **kw):
        Model = request.env["tmf.work"].sudo()
        if request.httprequest.method == "POST":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            data["@type"] = WORK_ORDER_TYPE
            vals = Model.from_tmf_json(data)
            vals["tmf_type_value"] = WORK_ORDER_TYPE
            if not vals.get("state"):
                vals["state"] = "acknowledged"
            rec = Model.create(vals)
            return self._json(self._wo_to_json(rec), status=201)
        domain = [("tmf_type_value", "=", WORK_ORDER_TYPE)]
        if kw.get("state"):
            domain.append(("state", "=", kw["state"]))
        return self._list_response("tmf.work", domain, self._wo_to_json, kw)

    @http.route(f"{API_BASE}/workOrder/<string:rid>", type="http", auth="public",
                methods=["GET", "PATCH", "DELETE"], csrf=False)
    def work_order_individual(self, rid, **kw):
        rec = self._wo_find(rid, WORK_ORDER_TYPE)
        if not rec:
            return self._error(404, "Not Found", f"WorkOrder {rid} not found")
        method = request.httprequest.method
        if method == "PATCH":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            data.pop("id", None)
            data.pop("href", None)
            data.pop("@type", None)
            vals = request.env["tmf.work"].sudo().from_tmf_json(data, partial=True)
            if vals:
                rec.write(vals)
            return self._json(self._wo_to_json(rec))
        if method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json(self._select_fields(self._wo_to_json(rec), kw.get("fields")))

    # ------------------------------------------------------------------
    # cancelWorkOrder (task resource)
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/cancelWorkOrder", type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def cancel_work_order_collection(self, **kw):
        Model = request.env["tmf.work"].sudo()
        if request.httprequest.method == "POST":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            wo_ref = data.get("workOrder") or {}
            wo_id = str((wo_ref or {}).get("id") or "").strip()
            if not wo_id:
                return self._error(400, "Bad Request", "Missing mandatory attribute: workOrder.id")
            work_order = self._wo_find(wo_id, WORK_ORDER_TYPE)
            if not work_order:
                return self._error(404, "Not Found", f"WorkOrder {wo_id} not found")
            work_order.write({"state": "cancelled"})
            task = Model.create({
                "name": data.get("name") or f"CancelWorkOrder-{wo_id}",
                "tmf_type_value": CANCEL_TYPE,
                "state": "done",
                "work_json": json.dumps({
                    "id": work_order.tmf_id,
                    "href": f"{self._wo_base_url()}/workOrder/{work_order.tmf_id}",
                    "@referredType": WORK_ORDER_TYPE,
                }, ensure_ascii=False),
                "note_json": json.dumps(
                    [{"text": data.get("cancellationReason") or ""}], ensure_ascii=False),
            })
            payload = self._wo_to_json(task)
            payload["workOrder"] = json.loads(task.work_json)
            payload["cancellationReason"] = data.get("cancellationReason") or ""
            return self._json(payload, status=201)
        domain = [("tmf_type_value", "=", CANCEL_TYPE)]
        return self._list_response("tmf.work", domain, self._wo_to_json, kw)

    @http.route(f"{API_BASE}/cancelWorkOrder/<string:rid>", type="http", auth="public",
                methods=["GET"], csrf=False)
    def cancel_work_order_individual(self, rid, **kw):
        rec = self._wo_find(rid, CANCEL_TYPE)
        if not rec:
            return self._error(404, "Not Found", f"CancelWorkOrder {rid} not found")
        return self._json(self._select_fields(self._wo_to_json(rec), kw.get("fields")))

    # ------------------------------------------------------------------
    # Hub
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/hub", type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("name", "like", "tmf697-")])
            return self._json([{"id": str(s.id), "callback": s.callback,
                                "query": s.query or ""} for s in subs])
        data = self._parse_json_body()
        callback = (data or {}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf697-workOrder-{callback}",
            "api_name": "workOrder",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("eventType") or "any",
            "content_type": "application/json",
        })
        return self._json({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""}, status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public",
                methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_kw):
        if not str(sid).isdigit():
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
        if not rec.exists() or not rec.name.startswith("tmf697-"):
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""})
