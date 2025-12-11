from odoo import http
from odoo.http import request
import json


class TMFServiceInventoryController(http.Controller):

    def _error(self, status, reason, message):
        body = json.dumps({
            "code": str(status),
            "reason": reason,
            "message": message,
        })
        return request.make_response(
            body,
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    # --- your existing /service endpoints here ---

    # ---------- HUB ENDPOINTS (TMF639 Service Inventory) ----------

    @http.route(
        '/tmf-api/serviceInventory/v4/hub',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_service_events(self, **kwargs):
        """Create subscription for Service events"""
        payload = request.jsonrequest or {}

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        sub = request.env['tmf.hub.subscription'].sudo().create({
            "api_name": "service",
            "callback": callback,
            "query": query,
        })

        return {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query,
            "@type": "EventSubscription"
        }

    @http.route(
        '/tmf-api/serviceInventory/v4/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_service_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'service')
        ])
        data = [{
            "id": str(s.id),
            "callback": s.callback,
            "query": s.query,
            "@type": "EventSubscription"
        } for s in subs]
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/serviceInventory/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_service_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
