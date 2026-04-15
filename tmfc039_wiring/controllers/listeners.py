# -*- coding: utf-8 -*-
"""TMFC039 AgreementManagement listener + hub controller."""

import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

TMFC039_LISTENER_BASE = "/tmfc039/listener"
TMFC039_HUB_BASE = "/tmfc039/hub"

PARTY_EVENTS = {
    "PartyCreateEvent", "PartyAttributeValueChangeEvent",
    "PartyStateChangeEvent", "PartyDeleteEvent",
    "IndividualCreateEvent", "IndividualAttributeValueChangeEvent",
    "IndividualStateChangeEvent", "IndividualDeleteEvent",
    "OrganizationCreateEvent", "OrganizationAttributeValueChangeEvent",
    "OrganizationStateChangeEvent", "OrganizationDeleteEvent",
}
PARTY_ROLE_EVENTS = {
    "PartyRoleCreateEvent", "PartyRoleAttributeValueChangeEvent",
    "PartyRoleStateChangeEvent", "PartyRoleDeleteEvent",
}
PRODUCT_SPEC_EVENTS = {
    "ProductSpecificationCreateEvent",
    "ProductSpecificationAttributeValueChangeEvent",
    "ProductSpecificationStateChangeEvent",
    "ProductSpecificationDeleteEvent",
    "ProductOfferingCreateEvent",
    "ProductOfferingAttributeValueChangeEvent",
    "ProductOfferingStateChangeEvent",
    "ProductOfferingDeleteEvent",
}


class TMFC039ListenerController(http.Controller):

    def _parse_json(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _json_response(self, payload=None, status=201):
        return request.make_response(
            json.dumps(payload or {}),
            status=status,
            headers=[("Content-Type", "application/json")],
        )

    def _dispatch(self, payload, allowed, handler_name, source):
        ev = str((payload or {}).get("eventType") or "").strip() if isinstance(payload, dict) else ""
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in allowed:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        tools = request.env["tmfc039.wiring.tools"].sudo()
        getattr(tools, handler_name)(payload)
        _logger.info("TMFC039: acknowledged %s event %s", source, ev)
        return self._json_response({}, status=201)

    @http.route(f"{TMFC039_LISTENER_BASE}/party",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_party(self, **_p):
        return self._dispatch(self._parse_json(), PARTY_EVENTS, "_handle_party_event", "party")

    @http.route(f"{TMFC039_LISTENER_BASE}/partyRole",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_party_role(self, **_p):
        return self._dispatch(self._parse_json(), PARTY_ROLE_EVENTS, "_handle_party_role_event", "partyRole")

    @http.route(f"{TMFC039_LISTENER_BASE}/productSpecification",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_product_spec(self, **_p):
        return self._dispatch(self._parse_json(), PRODUCT_SPEC_EVENTS, "_handle_product_specification_event", "productSpecification")

    @http.route(TMFC039_HUB_BASE,
                type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub_register(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc039-")])
            return self._json_response(
                [{"id": str(s.id), "name": s.name, "callback": s.callback,
                  "query": s.query or "", "api_name": s.api_name} for s in subs],
                status=200,
            )
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "agreement"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc039-{api_name}-{callback}",
            "api_name": api_name,
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("event_type") or "any",
            "content_type": "application/json",
        })
        return self._json_response(
            {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""},
            status=201,
        )

    @http.route(f"{TMFC039_HUB_BASE}/<string:sid>",
                type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc039-"):
                rec = None
        if not rec:
            return self._json_response({"error": f"Hub subscription {sid} not found"}, status=404)
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json_response(
            {"id": str(rec.id), "name": rec.name, "callback": rec.callback,
             "query": rec.query or "", "api_name": rec.api_name},
            status=200,
        )
