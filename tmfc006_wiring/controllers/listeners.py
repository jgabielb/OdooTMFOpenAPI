# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

RESOURCE_SPEC_EVENTS = {
    "ResourceSpecificationCreateEvent", "ResourceSpecificationChangeEvent",
    "ResourceSpecificationAttributeValueChangeEvent",
    "ResourceSpecificationStateChangeEvent", "ResourceSpecificationDeleteEvent",
}
ENTITY_SPEC_EVENTS = {
    "EntitySpecificationCreateEvent", "EntitySpecificationChangeEvent",
    "EntitySpecificationAttributeValueChangeEvent",
    "EntitySpecificationStateChangeEvent", "EntitySpecificationDeleteEvent",
}


class TMFC006ListenerController(http.Controller):
    """Listener endpoints for TMFC006 subscribed events.

    Stable URLs delegating to ``tmfc006.wiring.tools``.
    """

    def _apply(self, allowed, handler):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        ev = str(payload.get("eventType") or "").strip()
        if not ev:
            return request.make_response(
                json.dumps({"error": "Missing mandatory attribute: eventType"}),
                status=400, headers=[("Content-Type", "application/json")])
        if ev not in allowed:
            return request.make_response(
                json.dumps({"error": f"Listener event '{ev}' not supported"}),
                status=404, headers=[("Content-Type", "application/json")])
        tools = request.env["tmfc006.wiring.tools"].sudo()
        try:
            getattr(tools, handler)(payload)
        except Exception as exc:
            _logger.exception("TMFC006 listener %s failed", handler)
            return request.make_response(
                json.dumps({"error": str(exc)}), status=400,
                headers=[("Content-Type", "application/json")])
        return request.make_response(
            json.dumps({"status": "accepted"}), status=201,
            headers=[("Content-Type", "application/json")])

    @http.route(["/tmfc006/listener/resourceSpecification"],  # TMF634
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_resource_specification(self):
        return self._apply(RESOURCE_SPEC_EVENTS, "_handle_resource_catalog_event")

    @http.route(["/tmfc006/listener/entitySpecification"],  # TMF662
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_entity_specification(self):
        return self._apply(ENTITY_SPEC_EVENTS, "_handle_entity_catalog_event")
