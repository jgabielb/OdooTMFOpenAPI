# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class TMFC008HubController(http.Controller):
    """Minimal hub-registration façade for TMFC008.

    We keep TMF API URLs stable and reuse the generic
    ``tmf.hub.subscription`` model, similar to other TMFC wiring
    addons. This controller exists primarily to give the TMFC008
    checklist an evidence-backed hub entry point for Service events.
    """

    @http.route(
        [
            "/tmfc008/hub/serviceInventory",
        ],
        type="json",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def register_hub(self, **payload):
        subscription_model = request.env["tmf.hub.subscription"].sudo()
        # Pass 1: rely on tmf.hub.subscription to validate schema; we only
        # need a stable URL and basic create behaviour.
        subscription = subscription_model.create(payload)
        return {"id": subscription.id}


