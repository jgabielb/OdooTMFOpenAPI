# -*- coding: utf-8 -*-
"""TMFC023 PartyInteraction listener + hub controller.

Subscribed events: TMF720 DigitalIdentity, TMF632 PartyPrivacyAgreement.
On each accepted event, finds tmf.party.interaction records whose
related_party JSON mentions the affected id and re-resolves links.
"""

import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

TMFC023_LISTENER_BASE = "/tmfc023/listener"
TMFC023_HUB_BASE = "/tmfc023/hub"

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


class TMFC023ListenerController(http.Controller):

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

    def _event_type(self, payload):
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("eventType") or "").strip()

    def _extract_id(self, payload):
        if not isinstance(payload, dict):
            return ""
        event = payload.get("event")
        if isinstance(event, dict):
            for v in event.values():
                if isinstance(v, dict) and v.get("id"):
                    return str(v["id"]).strip()
        return str(payload.get("id") or "").strip()

    def _refresh(self, ref_id):
        if not ref_id:
            return
        Interaction = request.env["tmf.party.interaction"].sudo()
        try:
            affected = Interaction.search([("related_party", "ilike", ref_id)])
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC023: search for %s failed: %s", ref_id, exc)
            return
        if affected:
            try:
                affected._resolve_tmf_refs()
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception("TMFC023: re-resolve failed: %s", exc)

    @http.route(f"{TMFC023_LISTENER_BASE}/digitalIdentity",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_digital_identity(self, **_p):
        payload = self._parse_json()
        ev = self._event_type(payload)
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in IDENTITY_EVENTS:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        self._refresh(self._extract_id(payload))
        return self._json_response({}, status=201)

    @http.route(f"{TMFC023_LISTENER_BASE}/partyPrivacyAgreement",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_privacy_agreement(self, **_p):
        payload = self._parse_json()
        ev = self._event_type(payload)
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in AGREEMENT_EVENTS:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        self._refresh(self._extract_id(payload))
        return self._json_response({}, status=201)

    @http.route(TMFC023_HUB_BASE,
                type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub_register(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc023-")])
            return self._json_response(
                [{"id": str(s.id), "name": s.name, "callback": s.callback,
                  "query": s.query or "", "api_name": s.api_name} for s in subs],
                status=200,
            )
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "partyInteraction"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc023-{api_name}-{callback}",
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

    @http.route(f"{TMFC023_HUB_BASE}/<string:sid>",
                type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc023-"):
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
