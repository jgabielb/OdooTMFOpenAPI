from odoo import http
from odoo.http import request
import json


class TMFResourceInventoryController(http.Controller):

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

    # ---------- TMF638 /resource endpoints ----------

    @http.route(
        '/tmf-api/resourceInventory/v4/resource',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_resources(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 20))

        domain = []
        # simple filter examples (expand as needed)
        serial = params.get('serialNumber')
        if serial:
            domain.append(('name', '=', serial))

        status_param = params.get('resourceStatus')
        if status_param:
            domain.append(('resource_status', '=', status_param))

        resources = request.env['stock.lot'].sudo().search(
            domain, offset=offset, limit=limit, order='id desc'
        )
        data = [r.to_tmf_json() for r in resources]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/resourceInventory/v4/resource/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_resource(self, tmf_id, **params):
        res = request.env['stock.lot'].sudo().search(
            [('tmf_id', '=', tmf_id)], limit=1
        )
        if not res:
            return self._error(404, "Not Found", f"Resource {tmf_id} not found")

        data = res.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    # ---------- HUB ENDPOINTS (TMF638 Resource Inventory) ----------

    @http.route(
        '/tmf-api/resourceInventory/v4/hub',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_resource_events(self, **kwargs):
        """Create subscription for Resource events"""
        payload = request.jsonrequest or {}

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        sub = request.env['tmf.hub.subscription'].sudo().create({
            "api_name": "resource",
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
        '/tmf-api/resourceInventory/v4/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_resource_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'resource')
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
        '/tmf-api/resourceInventory/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_resource_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
