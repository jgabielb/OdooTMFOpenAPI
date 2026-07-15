# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

RESOURCE_INVENTORY_EVENTS = {
    "ResourceCreateEvent", "ResourceChangeEvent",
    "ResourceAttributeValueChangeEvent", "ResourceStateChangeEvent",
    "ResourceDeleteEvent",
}
SERVICE_INVENTORY_EVENTS = {
    "ServiceCreateEvent", "ServiceAttributeValueChangeEvent",
    "ServiceStateChangeEvent", "ServiceDeleteEvent",
}
SERVICE_CATALOG_EVENTS = {
    "ServiceSpecificationCreateEvent", "ServiceSpecificationChangeEvent",
    "ServiceSpecificationAttributeValueChangeEvent",
    "ServiceSpecificationStateChangeEvent", "ServiceSpecificationDeleteEvent",
}
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
SERVICE_ORDER_EVENTS = {
    "ServiceOrderCreateEvent", "ServiceOrderAttributeValueChangeEvent",
    "ServiceOrderStateChangeEvent", "ServiceOrderDeleteEvent",
}
GEO_ADDRESS_EVENTS = {
    "GeographicAddressCreateEvent", "GeographicAddressAttributeValueChangeEvent",
    "GeographicAddressStateChangeEvent", "GeographicAddressDeleteEvent",
}
GEO_SITE_EVENTS = {
    "GeographicSiteCreateEvent", "GeographicSiteAttributeValueChangeEvent",
    "GeographicSiteStateChangeEvent", "GeographicSiteDeleteEvent",
}
GEO_LOCATION_EVENTS = {
    "GeographicLocationCreateEvent", "GeographicLocationAttributeValueChangeEvent",
    "GeographicLocationStateChangeEvent", "GeographicLocationDeleteEvent",
}
PERMISSION_EVENTS = {
    "PermissionCreateEvent", "PermissionAttributeValueChangeEvent",
    "PermissionStateChangeEvent", "PermissionDeleteEvent",
}


class TMFC008ListenerController(http.Controller):
    """Listener endpoints for TMFC008 subscribed events.

    Each endpoint validates the event envelope against its YAML-derived
    allowed set, then delegates to ``tmfc008.wiring.tools``.
    """

    def _parse(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _resp(self, p=None, status=201):
        return request.make_response(json.dumps(p or {}), status=status,
                                     headers=[("Content-Type", "application/json")])

    def _apply(self, allowed, handler):
        payload = self._parse()
        if not isinstance(payload, dict):
            payload = {}
        ev = str(payload.get("eventType") or "").strip()
        if not ev:
            return self._resp({"error": "Missing mandatory attribute: eventType"},
                              status=400)
        if ev not in allowed:
            return self._resp({"error": f"Listener event '{ev}' not supported"},
                              status=404)
        tools = request.env["tmfc008.wiring.tools"].sudo()
        try:
            getattr(tools, handler)(payload)
        except Exception as exc:
            _logger.exception("TMFC008 listener %s failed", handler)
            return self._resp({"error": str(exc)}, status=400)
        return self._resp({"status": "accepted"}, status=201)

    @http.route(["/tmfc008/listener/resourceInventory"],  # TMF639
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_resource_inventory(self):
        return self._apply(RESOURCE_INVENTORY_EVENTS, "handle_resource_event")

    @http.route(["/tmfc008/listener/serviceInventory"],  # TMF638 self-subscriptions
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_service_inventory(self):
        return self._apply(SERVICE_INVENTORY_EVENTS, "handle_service_event")

    @http.route(["/tmfc008/listener/serviceCatalog"],  # TMF633
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_service_catalog(self):
        return self._apply(SERVICE_CATALOG_EVENTS, "handle_service_spec_event")

    @http.route(["/tmfc008/listener/party"],  # TMF632
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_party(self):
        return self._apply(PARTY_EVENTS, "handle_party_event")

    @http.route(["/tmfc008/listener/partyRole"],  # TMF669
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_party_role(self):
        return self._apply(PARTY_ROLE_EVENTS, "handle_party_role_event")

    @http.route(["/tmfc008/listener/serviceOrder"],  # TMF641
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_service_order(self):
        return self._apply(SERVICE_ORDER_EVENTS, "handle_service_order_event")

    @http.route(["/tmfc008/listener/geographicAddress"],  # TMF673
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_geographic_address(self):
        return self._apply(GEO_ADDRESS_EVENTS, "handle_geographic_address_event")

    @http.route(["/tmfc008/listener/geographicSite"],  # TMF674
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_geographic_site(self):
        return self._apply(GEO_SITE_EVENTS, "handle_geographic_site_event")

    @http.route(["/tmfc008/listener/geographicLocation"],  # TMF675
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_geographic_location(self):
        return self._apply(GEO_LOCATION_EVENTS, "handle_geographic_location_event")

    @http.route(["/tmfc008/listener/permission"],  # TMF672
                type="http", auth="none", methods=["POST"], csrf=False)
    def listener_permission(self):
        return self._apply(PERMISSION_EVENTS, "handle_permission_event")
