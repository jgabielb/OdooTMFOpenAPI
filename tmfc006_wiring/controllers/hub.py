# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class TMFC006HubController(http.Controller):
    """Minimal hub registration facade for TMFC006.

    We keep TMF API URLs stable and reuse the generic `tmf.hub.subscription`
    model used by other TMFC wiring addons. This controller exists mainly to
    give the TMFC006 checklist an evidence-backed hub entry point.
    """

    @http.route(
        [
            "/tmfc006/hub/serviceCatalog",
            "/tmfc006/hub/serviceQuality",
        ],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def register_hub(self):
        payload = request.jsonrequest or {}
        subscription_model = request.env["tmf.hub.subscription"].sudo()
        # Pass 1: trust payload to contain at least callback and query fields; we do not
        # enforce schema beyond what `tmf.hub.subscription` already validates.
        subscription = subscription_model.create(payload)
        return {"id": subscription.id}
