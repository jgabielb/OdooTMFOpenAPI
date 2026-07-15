# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TMFC008ListenerController(http.Controller):
    """Listener endpoints for TMFC008 subscribed events.

    Each endpoint accepts a JSON payload, delegates to
    ``tmfc008.wiring.tools``, and returns a simple acknowledgement.
    """

    def _parse(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _apply(self, handler):
        payload = self._parse()
        tools = request.env["tmfc008.wiring.tools"].sudo()
        try:
            getattr(tools, handler)(payload if isinstance(payload, dict) else {})
        except Exception as exc:
            _logger.exception("TMFC008 listener %s failed", handler)
            return request.make_response(
                json.dumps({"error": str(exc)}), status=400,
                headers=[("Content-Type", "application/json")])
        return request.make_response(
            json.dumps({"status": "accepted"}), status=201,
            headers=[("Content-Type", "application/json")])

    @http.route(["/tmfc008/listener/resourceInventory"],  # TMF639
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_resource_inventory(self):
        return self._apply("handle_resource_event")

    @http.route(["/tmfc008/listener/serviceInventory"],  # TMF638 self-subscriptions
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_service_inventory(self):
        return self._apply("handle_service_event")

    @http.route(["/tmfc008/listener/serviceCatalog"],  # TMF633
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_service_catalog(self):
        return self._apply("handle_service_spec_event")

    @http.route(["/tmfc008/listener/party"],  # TMF632
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_party(self):
        return self._apply("handle_party_event")

    @http.route(["/tmfc008/listener/partyRole"],  # TMF669
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_party_role(self):
        return self._apply("handle_party_role_event")

    @http.route(["/tmfc008/listener/serviceOrder"],  # TMF641
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_service_order(self):
        return self._apply("handle_service_order_event")

    @http.route(["/tmfc008/listener/geographicAddress"],  # TMF673
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_geographic_address(self):
        return self._apply("handle_geographic_address_event")

    @http.route(["/tmfc008/listener/geographicSite"],  # TMF674
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_geographic_site(self):
        return self._apply("handle_geographic_site_event")

    @http.route(["/tmfc008/listener/geographicLocation"],  # TMF675
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_geographic_location(self):
        return self._apply("handle_geographic_location_event")

    @http.route(["/tmfc008/listener/permission"],  # TMF672
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_permission(self):
        return self._apply("handle_permission_event")
