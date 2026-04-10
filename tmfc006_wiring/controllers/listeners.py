# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class TMFC006ListenerController(http.Controller):
    """Listener endpoints for TMFC006 subscribed events.

    Pass 1 creates stable URLs and delegates to `tmfc006.wiring.tools` without
    enforcing aggressive reconciliation. This lets other TMFCs and external
    systems rely on these callbacks while we incrementally harden the logic.
    """

    @http.route(
        [
            "/tmfc006/listener/resourceSpecification",  # TMF634 ResourceCatalogManagement
        ],
        type="json",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_resource_specification(self, **payload):
        tools = request.env["tmfc006.wiring.tools"].sudo()
        tools._handle_resource_catalog_event(payload)
        return {"status": "accepted"}

    @http.route(
        [
            "/tmfc006/listener/entitySpecification",  # TMF662 EntityCatalogManagement
        ],
        type="json",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def listener_entity_specification(self, **payload):
        tools = request.env["tmfc006.wiring.tools"].sudo()
        tools._handle_entity_catalog_event(payload)
        return {"status": "accepted"}
