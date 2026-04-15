# -*- coding: utf-8 -*-
"""TMFC022 PartyPrivacy listener + hub controller.

Subscribed events: TMF632 Party, TMF720 DigitalIdentity. On each
accepted event, locates tmf.party.privacy.agreement records whose JSON
references the affected id and re-runs ``_resolve_tmf_refs``.
"""

import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

TMFC022_LISTENER_BASE = "/tmfc022/listener"
TMFC022_HUB_BASE = "/tmfc022/hub"

PARTY_EVENTS = {
    "PartyCreateEvent", "PartyAttributeValueChangeEvent",
    "PartyStateChangeEvent", "PartyDeleteEvent",
}
IDENTITY_EVENTS = {
    "DigitalIdentityCreateEvent", "DigitalIdentityAttributeValueChangeEvent",
    "DigitalIdentityStateChangeEvent", "DigitalIdentityDeleteEvent",
}


class TMFC022ListenerController(http.Controller):

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

    def _refresh(self, json_field, ref_id):
        if not ref_id:
            return
        Agreement = request.env["tmf.party.privacy.agreement"].sudo()
        try:
            affected = Agreement.search([(json_field, "ilike", ref_id)])
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC022: search %s for %s failed: %s", json_field, ref_id, exc)
            return
        if affected:
            try:
                affected._resolve_tmf_refs()
            except Exception as exc:  # pragma: no cover - best-effort
                _logger.exception("TMFC022: re-resolve failed: %s", exc)

    @http.route(f"{TMFC022_LISTENER_BASE}/party",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_party(self, **_p):
        payload = self._parse_json()
        ev = self._event_type(payload)
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in PARTY_EVENTS:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        self._refresh("engaged_party_json", self._extract_id(payload))
        return self._json_response({}, status=201)

    @http.route(f"{TMFC022_LISTENER_BASE}/digitalIdentity",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_digital_identity(self, **_p):
        payload = self._parse_json()
        ev = self._event_type(payload)
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in IDENTITY_EVENTS:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        self._refresh("privacy_profile_json", self._extract_id(payload))
        return self._json_response({}, status=201)

    @http.route(TMFC022_HUB_BASE,
                type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub_register(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc022-")])
            return self._json_response(
                [{"id": str(s.id), "name": s.name, "callback": s.callback,
                  "query": s.query or "", "api_name": s.api_name} for s in subs],
                status=200,
            )
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "partyPrivacyAgreement"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc022-{api_name}-{callback}",
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

    @http.route(f"{TMFC022_HUB_BASE}/<string:sid>",
                type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc022-"):
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
