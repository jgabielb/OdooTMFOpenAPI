# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TMFC006ListenerController(http.Controller):
    """Listener endpoints for TMFC006 subscribed events.

    Stable URLs delegating to ``tmfc006.wiring.tools``.
    """

    def _apply(self, handler):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            payload = {}
        tools = request.env["tmfc006.wiring.tools"].sudo()
        try:
            getattr(tools, handler)(payload if isinstance(payload, dict) else {})
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
        return self._apply("_handle_resource_catalog_event")

    @http.route(["/tmfc006/listener/entitySpecification"],  # TMF662
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_entity_specification(self):
        return self._apply("_handle_entity_catalog_event")
