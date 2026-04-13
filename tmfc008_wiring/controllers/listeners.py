# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class TMFC008ListenerController(http.Controller):
    """Listener endpoints for TMFC008 subscribed events.

    Pass 1 keeps behaviour extremely conservative: each endpoint
    accepts a JSON payload, delegates to ``tmfc008.wiring.tools``, and
    returns a simple acknowledgement. All reconciliation is currently
    a no-op so that URLs remain stable while we add evidence-backed
    wiring in later passes.
    """

    @http.route(
        [
            "/tmfc008/listener/resourceInventory",  # TMF639 ResourceInventoryManagement
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_resource_inventory(self):
        payload = request.jsonrequest or {}
        tools = request.env["tmfc008.wiring.tools"].sudo()
        tools.handle_resource_event(payload)
        return {"status": "accepted"}

    @http.route(
        [
            "/tmfc008/listener/serviceInventory",  # TMF638 self-subscriptions
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_service_inventory(self):
        payload = request.jsonrequest or {}
        tools = request.env["tmfc008.wiring.tools"].sudo()
        tools.handle_service_event(payload)
        return {"status": "accepted"}

    @http.route(
        [
            "/tmfc008/listener/serviceCatalog",  # TMF633 ServiceCatalogManagement
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_service_catalog(self):
        payload = request.jsonrequest or {}
        tools = request.env["tmfc008.wiring.tools"].sudo()
        tools.handle_service_spec_event(payload)
        return {"status": "accepted"}

    @http.route(
        [
            "/tmfc008/listener/party",  # TMF632 PartyManagement
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_party(self):
        payload = request.jsonrequest or {}
        tools = request.env["tmfc008.wiring.tools"].sudo()
        tools.handle_party_event(payload)
        return {"status": "accepted"}

    @http.route(
        [
            "/tmfc008/listener/partyRole",  # TMF669 PartyRoleManagement
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_party_role(self):
        payload = request.jsonrequest or {}
        tools = request.env["tmfc008.wiring.tools"].sudo()
        tools.handle_party_role_event(payload)
        return {"status": "accepted"}

    @http.route(
        [
            "/tmfc008/listener/serviceOrder",  # TMF641 ServiceOrderingManagement
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_service_order(self):
        payload = request.jsonrequest or {}
        tools = request.env["tmfc008.wiring.tools"].sudo()
        tools.handle_service_order_event(payload)
        return {"status": "accepted"}


