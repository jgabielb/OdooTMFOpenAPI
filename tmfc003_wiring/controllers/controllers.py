"""
TMFC003 Listener Controller
============================

Exposes HTTP listener endpoints for TMF641 (ServiceOrder) and TMF652
(ResourceOrder) event notifications, plus a hub-registration endpoint so
other components can subscribe to TMFC003-published TMF622/TMF701 events.

Route structure
---------------
POST  /tmfc003/listener/serviceOrder
    Accepts TMF641 events:
      - ServiceOrderStateChangeEvent
      - ServiceOrderCreateEvent
      - ServiceOrderAttributeValueChangeEvent
      - ServiceOrderDeleteEvent

POST  /tmfc003/listener/resourceOrder
    Accepts TMF652 events:
      - ResourceOrderStateChangeEvent
      - ResourceOrderCreateEvent
      - ResourceOrderAttributeValueChangeEvent
      - ResourceOrderDeleteEvent

GET / POST  /tmfc003/hub
    Hub registration for TMFC003 outbound TMF622/TMF701 subscriptions.

DELETE  /tmfc003/hub/<sid>
    Unregister a hub subscription.

Design notes
------------
- Routes are auth="public" (same pattern as tmfc005_wiring) because hub
  callbacks must be reachable without session authentication.
- CSRF disabled for all routes (webhook consumers do not carry CSRF tokens).
- All dispatching is delegated to tmfc003.wiring.tools to keep the
  controller thin and testable.
"""

import json
import logging

from odoo import http
from odoo.http import request

from ..models.wiring import TMFC003_SERVICE_ORDER_EVENTS, TMFC003_RESOURCE_ORDER_EVENTS

_logger = logging.getLogger(__name__)

TMFC003_LISTENER_BASE = "/tmfc003/listener"
TMFC003_HUB_BASE = "/tmfc003/hub"


class TMFC003ListenerController(http.Controller):
    """Listener and hub controller for TMFC003 event processing."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
            body,
            status=status,
            headers=[("Content-Type", "application/json")],
        )

    def _get_event_type(self, payload):
        """Extract eventType from the payload envelope."""
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("eventType") or "").strip()

    # ------------------------------------------------------------------
    # TMF641 ServiceOrder listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC003_LISTENER_BASE}/serviceOrder",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_service_order(self, **_params):
        """Receive TMF641 ServiceOrder events and dispatch to wiring tools.

        Accepted events:
        - ServiceOrderStateChangeEvent
        - ServiceOrderCreateEvent
        - ServiceOrderAttributeValueChangeEvent
        - ServiceOrderDeleteEvent
        """
        payload = self._parse_json()
        event_name = self._get_event_type(payload)

        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )

        if event_name not in TMFC003_SERVICE_ORDER_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /serviceOrder"},
                status=404,
            )

        try:
            request.env["tmfc003.wiring.tools"].sudo().handle_service_order_event(
                event_name, payload
            )
        except Exception as exc:
            _logger.exception(
                "TMFC003: error handling service order event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )

        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # TMF652 ResourceOrder listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC003_LISTENER_BASE}/resourceOrder",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_resource_order(self, **_params):
        """Receive TMF652 ResourceOrder events and dispatch to wiring tools.

        Accepted events:
        - ResourceOrderStateChangeEvent
        - ResourceOrderCreateEvent
        - ResourceOrderAttributeValueChangeEvent
        - ResourceOrderDeleteEvent
        """
        payload = self._parse_json()
        event_name = self._get_event_type(payload)

        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )

        if event_name not in TMFC003_RESOURCE_ORDER_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /resourceOrder"},
                status=404,
            )

        try:
            request.env["tmfc003.wiring.tools"].sudo().handle_resource_order_event(
                event_name, payload
            )
        except Exception as exc:
            _logger.exception(
                "TMFC003: error handling resource order event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )

        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # Hub registration endpoints
    # ------------------------------------------------------------------

    @http.route(
        TMFC003_HUB_BASE,
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def hub_register(self, **_params):
        """Hub registration endpoint for TMFC003-published events.

        POST: Register a new subscriber for TMFC003 events (TMF622 / TMF701).
        GET:  List current TMFC003 hub subscriptions.
        """
        if request.httprequest.method == "GET":
            subs = (
                request.env["tmf.hub.subscription"]
                .sudo()
                .search([("name", "like", "tmfc003-")])
            )
            result = [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "callback": s.callback,
                    "query": s.query or "",
                    "api_name": s.api_name,
                }
                for s in subs
            ]
            return self._json_response(result, status=200)

        # POST
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response(
                {"error": "Missing mandatory attribute: callback"}, status=400
            )

        api_name = data.get("api_name") or "productOrder"
        rec = (
            request.env["tmf.hub.subscription"]
            .sudo()
            .create({
                "name": f"tmfc003-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": data.get("event_type") or "any",
                "content_type": "application/json",
            })
        )
        return self._json_response(
            {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""},
            status=201,
        )

    @http.route(
        f"{TMFC003_HUB_BASE}/<string:sid>",
        type="http",
        auth="public",
        methods=["GET", "DELETE"],
        csrf=False,
    )
    def hub_detail(self, sid, **_params):
        """Get or unregister a specific TMFC003 hub subscription."""
        rec = None
        if str(sid).isdigit():
            rec = (
                request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            )
            if not rec.exists() or not rec.name.startswith("tmfc003-"):
                rec = None

        if not rec:
            return self._json_response(
                {"error": f"Hub subscription {sid} not found"}, status=404
            )

        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)

        # GET
        return self._json_response(
            {
                "id": str(rec.id),
                "name": rec.name,
                "callback": rec.callback,
                "query": rec.query or "",
                "api_name": rec.api_name,
            },
            status=200,
        )
