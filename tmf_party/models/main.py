from odoo import http
from odoo.http import request
import json


class TMFProductCatalogController(http.Controller):

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

    # ---------- HUB ENDPOINTS (TMF620 Product Catalog) ----------

    @http.route(
        '/tmf-api/productCatalogManagement/v4/hub',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_catalog_events(self, **kwargs):
        """Create subscription for Product Catalog events"""
        payload = request.jsonrequest or {}

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        sub = request.env['tmf.hub.subscription'].sudo().create({
            "api_name": "productCatalog",
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
        '/tmf-api/productCatalogManagement/v4/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_catalog_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'productCatalog')
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
        '/tmf-api/productCatalogManagement/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_catalog_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
