# -*- coding: utf-8 -*-
"""TMFC031 BillCalculation — ODA listener + hub façade.

Subscribed events per TMFC031 YAML: TMF635 usage create/AVC/delete/stateChange
and usageSpecification create/AVC/delete.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

BASE_L = "/tmfc031/listener"
BASE_H = "/tmfc031/hub"

USAGE_EVENTS = {
    "UsageCreateEvent", "UsageAttributeValueChangeEvent",
    "UsageStateChangeEvent", "UsageDeleteEvent",
}
USAGE_SPEC_EVENTS = {
    "UsageSpecificationCreateEvent", "UsageSpecificationAttributeValueChangeEvent",
    "UsageSpecificationChangeEvent", "UsageSpecificationDeleteEvent",
}


class TMFC031ListenerController(http.Controller):
    def _parse(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _resp(self, p=None, status=201):
        return request.make_response(json.dumps(p or {}), status=status,
                                     headers=[("Content-Type", "application/json")])

    def _dispatch(self, payload, allowed, handler):
        ev = str((payload or {}).get("eventType") or "").strip() if isinstance(payload, dict) else ""
        if not ev:
            return self._resp({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in allowed:
            return self._resp({"error": f"Listener event '{ev}' not supported"}, status=404)
        try:
            getattr(request.env["tmfc031.wiring.tools"].sudo(), handler)(payload)
        except Exception as exc:
            _logger.exception("TMFC031 listener %s failed", handler)
            return self._resp({"error": str(exc)}, status=400)
        return self._resp({}, status=201)

    @http.route(f"{BASE_L}/usage", type="http", auth="public", methods=["POST"], csrf=False)
    def l_usage(self, **_p):
        return self._dispatch(self._parse(), USAGE_EVENTS, "handle_usage_event")

    @http.route(f"{BASE_L}/usageSpecification", type="http", auth="public",
                methods=["POST"], csrf=False)
    def l_usage_spec(self, **_p):
        return self._dispatch(self._parse(), USAGE_SPEC_EVENTS,
                              "handle_usage_specification_event")

    @http.route(BASE_H, type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("name", "like", "tmfc031-")])
            return self._resp([{"id": str(s.id), "name": s.name, "callback": s.callback,
                                "query": s.query or "", "api_name": s.api_name}
                               for s in subs], status=200)
        data = self._parse()
        cb = data.get("callback")
        if not cb:
            return self._resp({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "appliedCustomerBillingRate"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc031-{api_name}-{cb}", "api_name": api_name, "callback": cb,
            "query": data.get("query", ""), "event_type": data.get("event_type") or "any",
            "content_type": "application/json",
        })
        return self._resp({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""}, status=201)

    @http.route(f"{BASE_H}/<string:sid>", type="http", auth="public",
                methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc031-"):
                rec = None
        if not rec:
            return self._resp({"error": f"Hub subscription {sid} not found"}, status=404)
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._resp({"id": str(rec.id), "name": rec.name, "callback": rec.callback,
                           "query": rec.query or "", "api_name": rec.api_name}, status=200)
