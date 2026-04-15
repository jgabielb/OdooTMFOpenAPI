# -*- coding: utf-8 -*-
"""TMFC028 Party listener + hub controller.

TMFC028 keeps res.partner up to date through reverse Many2one /
One2many relations on tmf.digital.identity, tmf.party.privacy.agreement
and tmf.party.interaction. The listener routes accept TMF720 / Privacy
/ Interaction events and validate envelopes; the actual record refresh
is owned by the source-component wiring (TMFC020/022/023). This
controller exists to evidence subscription completeness for TMFC028.
"""

import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

TMFC028_LISTENER_BASE = "/tmfc028/listener"
TMFC028_HUB_BASE = "/tmfc028/hub"

IDENTITY_EVENTS = {
    "DigitalIdentityCreateEvent", "DigitalIdentityAttributeValueChangeEvent",
    "DigitalIdentityStateChangeEvent", "DigitalIdentityDeleteEvent",
}
AGREEMENT_EVENTS = {
    "PartyPrivacyAgreementCreateEvent",
    "PartyPrivacyAgreementAttributeValueChangeEvent",
    "PartyPrivacyAgreementStateChangeEvent",
    "PartyPrivacyAgreementDeleteEvent",
}
INTERACTION_EVENTS = {
    "PartyInteractionCreateEvent",
    "PartyInteractionAttributeValueChangeEvent",
    "PartyInteractionStateChangeEvent",
    "PartyInteractionDeleteEvent",
}


class TMFC028ListenerController(http.Controller):

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

    def _ack(self, payload, allowed_events, source):
        ev = str((payload or {}).get("eventType") or "").strip() if isinstance(payload, dict) else ""
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in allowed_events:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        _logger.info("TMFC028: acknowledged %s event %s", source, ev)
        # res.partner reverse relations refresh automatically; no resolver needed.
        return self._json_response({}, status=201)

    @http.route(f"{TMFC028_LISTENER_BASE}/digitalIdentity",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_digital_identity(self, **_p):
        return self._ack(self._parse_json(), IDENTITY_EVENTS, "digitalIdentity")

    @http.route(f"{TMFC028_LISTENER_BASE}/partyPrivacyAgreement",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_privacy_agreement(self, **_p):
        return self._ack(self._parse_json(), AGREEMENT_EVENTS, "partyPrivacyAgreement")

    @http.route(f"{TMFC028_LISTENER_BASE}/partyInteraction",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_party_interaction(self, **_p):
        return self._ack(self._parse_json(), INTERACTION_EVENTS, "partyInteraction")

    @http.route(TMFC028_HUB_BASE,
                type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub_register(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc028-")])
            return self._json_response(
                [{"id": str(s.id), "name": s.name, "callback": s.callback,
                  "query": s.query or "", "api_name": s.api_name} for s in subs],
                status=200,
            )
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "party"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc028-{api_name}-{callback}",
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

    @http.route(f"{TMFC028_HUB_BASE}/<string:sid>",
                type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc028-"):
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
