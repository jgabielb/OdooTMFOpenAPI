# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

BASE_L = "/tmfc037/listener"
BASE_H = "/tmfc037/hub"
PARTY_EVENTS = {
    "PartyCreateEvent", "PartyAttributeValueChangeEvent", "PartyStateChangeEvent", "PartyDeleteEvent",
    "IndividualCreateEvent", "IndividualAttributeValueChangeEvent", "IndividualStateChangeEvent", "IndividualDeleteEvent",
    "OrganizationCreateEvent", "OrganizationAttributeValueChangeEvent", "OrganizationStateChangeEvent", "OrganizationDeleteEvent",
}
PARTY_ROLE_EVENTS = {
    "PartyRoleCreateEvent", "PartyRoleAttributeValueChangeEvent", "PartyRoleStateChangeEvent", "PartyRoleDeleteEvent",
}


class TMFC037ListenerController(http.Controller):
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
        getattr(request.env["tmfc037.wiring.tools"].sudo(), handler)(payload)
        return self._resp({}, status=201)

    @http.route(f"{BASE_L}/party", type="http", auth="public", methods=["POST"], csrf=False)
    def l_party(self, **_p):
        return self._dispatch(self._parse(), PARTY_EVENTS, "_handle_party_event")

    @http.route(f"{BASE_L}/partyRole", type="http", auth="public", methods=["POST"], csrf=False)
    def l_party_role(self, **_p):
        return self._dispatch(self._parse(), PARTY_ROLE_EVENTS, "_handle_party_role_event")

    @http.route(BASE_H, type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc037-")])
            return self._resp([{"id": str(s.id), "name": s.name, "callback": s.callback,
                                 "query": s.query or "", "api_name": s.api_name} for s in subs], status=200)
        data = self._parse()
        cb = data.get("callback")
        if not cb:
            return self._resp({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "performanceReport"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc037-{api_name}-{cb}", "api_name": api_name, "callback": cb,
            "query": data.get("query", ""), "event_type": data.get("event_type") or "any",
            "content_type": "application/json",
        })
        return self._resp({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}, status=201)

    @http.route(f"{BASE_H}/<string:sid>", type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc037-"):
                rec = None
        if not rec:
            return self._resp({"error": f"Hub subscription {sid} not found"}, status=404)
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._resp({"id": str(rec.id), "name": rec.name, "callback": rec.callback,
                            "query": rec.query or "", "api_name": rec.api_name}, status=200)
