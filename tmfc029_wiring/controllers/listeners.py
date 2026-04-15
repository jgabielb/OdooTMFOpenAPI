# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from ..models.wiring_tools import (
    TMFC029_BILLING_ACCOUNT_EVENTS,
    TMFC029_CUSTOMER_BILL_EVENTS,
    TMFC029_PARTY_EVENTS,
)


_logger = logging.getLogger(__name__)

TMFC029_LISTENER_BASE = "/tmfc029/listener"
TMFC029_HUB_BASE = "/tmfc029/hub"


class TMFC029ListenerController(http.Controller):

    def _parse_json(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _json_response(self, payload=None, status=201):
        body = json.dumps(payload or {})
        return request.make_response(
            body, status=status, headers=[("Content-Type", "application/json")]
        )

    def _event_type(self, payload):
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("eventType") or "").strip()

    def _dispatch(self, handler_name, allowed_events, payload):
        ev = self._event_type(payload)
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in allowed_events:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        try:
            handler = getattr(request.env["tmfc029.wiring.tools"].sudo(), handler_name)
            handler(ev, payload)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("TMFC029: handler %s failed: %s", handler_name, exc)
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )
        return self._json_response({}, status=201)

    @http.route(
        f"{TMFC029_LISTENER_BASE}/billingAccount",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    def listener_billing_account(self, **_p):
        return self._dispatch(
            "handle_billing_account_event",
            TMFC029_BILLING_ACCOUNT_EVENTS,
            self._parse_json(),
        )

    @http.route(
        f"{TMFC029_LISTENER_BASE}/customerBill",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    def listener_customer_bill(self, **_p):
        return self._dispatch(
            "handle_customer_bill_event",
            TMFC029_CUSTOMER_BILL_EVENTS,
            self._parse_json(),
        )

    @http.route(
        f"{TMFC029_LISTENER_BASE}/party",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    def listener_party(self, **_p):
        return self._dispatch(
            "handle_party_event",
            TMFC029_PARTY_EVENTS,
            self._parse_json(),
        )

    @http.route(
        TMFC029_HUB_BASE,
        type="http", auth="public", methods=["GET", "POST"], csrf=False,
    )
    def hub_register(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc029-")])
            return self._json_response(
                [
                    {"id": str(s.id), "name": s.name, "callback": s.callback,
                     "query": s.query or "", "api_name": s.api_name}
                    for s in subs
                ],
                status=200,
            )
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "payment"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc029-{api_name}-{callback}",
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

    @http.route(
        f"{TMFC029_HUB_BASE}/<string:sid>",
        type="http", auth="public", methods=["GET", "DELETE"], csrf=False,
    )
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc029-"):
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
