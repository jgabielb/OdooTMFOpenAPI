"""TMFC007 Listener and hub controller.

Exposes HTTP listener endpoints for the TMFC007-subscribed domains, plus a
lightweight hub-registration surface for ServiceOrder/ProcessFlow events.

Listener routes (scaffolding only at this stage):

POST  /tmfc007/listener/resourceOrder
    Accepts TMF652 events:
      - ResourceOrderStateChangeEvent
      - ResourceOrderAttributeValueChangeEvent
      - ResourceOrderInformationRequiredEvent
      - CancelResourceOrderStateChangeEvent
      - CancelResourceOrderInformationRequiredEvent

POST  /tmfc007/listener/serviceQualification
    Accepts TMF645 events:
      - CheckServiceQualificationStateChangeEvent
      - QueryServiceQualificationStateChangeEvent

POST  /tmfc007/listener/communicationMessage
    Accepts TMF681 events:
      - CommunicationMessageStateChangeEvent

POST  /tmfc007/listener/workOrder
    Accepts TMF697 events:
      - WorkOrderStateChangeEvent

Hub routes (for outbound TMF641/TMF701 events):

GET/POST  /tmfc007/hub
    Register or list subscribers for TMFC007-published TMF641/TMF701 events.

GET/DELETE  /tmfc007/hub/<sid>
    Inspect or remove a single TMFC007 hub subscription.
"""

import json
import logging

from odoo import http
from odoo.http import request

from ..models.wiring import (
    TMFC007_RESOURCE_ORDER_EVENTS,
    TMFC007_SERVICE_QUALIFICATION_EVENTS,
    TMFC007_COMMUNICATION_EVENTS,
    TMFC007_WORK_ORDER_EVENTS,
    TMFC007_PARTY_EVENTS,
    TMFC007_PARTY_ROLE_EVENTS,
)


_logger = logging.getLogger(__name__)


TMFC007_LISTENER_BASE = "/tmfc007/listener"
TMFC007_HUB_BASE = "/tmfc007/hub"


class TMFC007ListenerController(http.Controller):
    """Listener and hub controller for TMFC007 wiring."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_json(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:  # pragma: no cover - defensive
            return {}

    def _json_response(self, payload=None, status=201):
        body = json.dumps(payload or {})
        return request.make_response(
            body,
            status=status,
            headers=[("Content-Type", "application/json")],
        )

    def _get_event_type(self, payload):
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("eventType") or "").strip()

    # ------------------------------------------------------------------
    # TMF652 ResourceOrder listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC007_LISTENER_BASE}/resourceOrder",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_resource_order(self, **_params):
        payload = self._parse_json()
        event_name = self._get_event_type(payload)

        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )

        if event_name not in TMFC007_RESOURCE_ORDER_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /resourceOrder"},
                status=404,
            )

        try:
            request.env["tmfc007.wiring.tools"].sudo().handle_resource_order_event(
                event_name, payload
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "TMFC007: error handling resource order event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )

        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # TMF645 ServiceQualification listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC007_LISTENER_BASE}/serviceQualification",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_service_qualification(self, **_params):
        payload = self._parse_json()
        event_name = self._get_event_type(payload)

        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )

        if event_name not in TMFC007_SERVICE_QUALIFICATION_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /serviceQualification"},
                status=404,
            )

        try:
            request.env["tmfc007.wiring.tools"].sudo().handle_service_qualification_event(
                event_name, payload
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "TMFC007: error handling service qualification event %s: %s",
                event_name,
                exc,
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )

        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # TMF681 Communication listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC007_LISTENER_BASE}/communicationMessage",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_communication(self, **_params):
        payload = self._parse_json()
        event_name = self._get_event_type(payload)

        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )

        if event_name not in TMFC007_COMMUNICATION_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /communicationMessage"},
                status=404,
            )

        try:
            request.env["tmfc007.wiring.tools"].sudo().handle_communication_event(
                event_name, payload
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "TMFC007: error handling communication event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )

        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # TMF697 WorkOrder listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC007_LISTENER_BASE}/workOrder",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_work_order(self, **_params):
        payload = self._parse_json()
        event_name = self._get_event_type(payload)

        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )

        if event_name not in TMFC007_WORK_ORDER_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /workOrder"},
                status=404,
            )

        try:
            request.env["tmfc007.wiring.tools"].sudo().handle_work_order_event(
                event_name, payload
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "TMFC007: error handling work order event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )

        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # TMF632 Party listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC007_LISTENER_BASE}/party",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_party(self, **_params):
        payload = self._parse_json()
        event_name = self._get_event_type(payload)
        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )
        if event_name not in TMFC007_PARTY_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /party"},
                status=404,
            )
        try:
            request.env["tmfc007.wiring.tools"].sudo().handle_party_event(
                event_name, payload
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "TMFC007: error handling party event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )
        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # TMF669 PartyRole listener
    # ------------------------------------------------------------------

    @http.route(
        f"{TMFC007_LISTENER_BASE}/partyRole",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_party_role(self, **_params):
        payload = self._parse_json()
        event_name = self._get_event_type(payload)
        if not event_name:
            return self._json_response(
                {"error": "Missing mandatory attribute: eventType"}, status=400
            )
        if event_name not in TMFC007_PARTY_ROLE_EVENTS:
            return self._json_response(
                {"error": f"Listener event '{event_name}' not supported by /partyRole"},
                status=404,
            )
        try:
            request.env["tmfc007.wiring.tools"].sudo().handle_party_role_event(
                event_name, payload
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "TMFC007: error handling partyRole event %s: %s", event_name, exc
            )
            return self._json_response(
                {"error": "Internal error processing event", "detail": str(exc)}, status=500
            )
        return self._json_response({}, status=201)

    # ------------------------------------------------------------------
    # Hub registration endpoints (TMF641/TMF701 outbound events)
    # ------------------------------------------------------------------

    @http.route(
        TMFC007_HUB_BASE,
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def hub_register(self, **_params):
        """Hub registration endpoint for TMFC007-published events.

        POST: Register a new subscriber for TMFC007 events ("serviceOrder" or
              "processFlow"/"taskFlow", matching TMF641/TMF701).
        GET:  List current TMFC007 hub subscriptions.
        """

        if request.httprequest.method == "GET":
            subs = (
                request.env["tmf.hub.subscription"]
                .sudo()
                .search([("name", "like", "tmfc007-")])
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

        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response(
                {"error": "Missing mandatory attribute: callback"}, status=400
            )

        api_name = data.get("api_name") or "serviceOrder"
        rec = (
            request.env["tmf.hub.subscription"]
            .sudo()
            .create(
                {
                    "name": f"tmfc007-{api_name}-{callback}",
                    "api_name": api_name,
                    "callback": callback,
                    "query": data.get("query", ""),
                    "event_type": data.get("event_type") or "any",
                    "content_type": "application/json",
                }
            )
        )
        return self._json_response(
            {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""},
            status=201,
        )

    @http.route(
        f"{TMFC007_HUB_BASE}/<string:sid>",
        type="http",
        auth="public",
        methods=["GET", "DELETE"],
        csrf=False,
    )
    def hub_detail(self, sid, **_params):
        """Inspect or remove a TMFC007 hub subscription."""

        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc007-"):
                rec = None

        if not rec:
            return self._json_response(
                {"error": f"Hub subscription {sid} not found"}, status=404
            )

        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)

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


