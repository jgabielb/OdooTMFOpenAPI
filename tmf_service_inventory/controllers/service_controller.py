from odoo import http
from odoo.http import request
import json


class TMFServiceController(http.Controller):

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

    # =======================================================
    # TMF639: Service Inventory – Service list & retrieve
    # =======================================================

    @http.route(
        '/tmf-api/serviceInventory/v4/service',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_services(self, **params):
        domain = []

        # Basic pagination
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        # Simple filter: ?relatedParty.id=<tmf_id or db id>
        related_party_id = params.get('relatedParty.id')
        if related_party_id:
            domain = ['|',
                      ('partner_id.tmf_id', '=', related_party_id),
                      ('partner_id', '=', int(related_party_id)) if related_party_id.isdigit() else ('id', '=', 0)
                     ]

        services = request.env['tmf.service'].sudo().search(
            domain, offset=offset, limit=limit
        )

        data = [s.to_tmf_json() for s in services]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/serviceInventory/v4/service/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_service(self, tmf_id, **params):
        service = request.env['tmf.service'].sudo().search(
            [('tmf_id', '=', tmf_id)], limit=1
        )
        if not service:
            return self._error(404, "Not Found", f"Service {tmf_id} not found")

        data = service.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # TMF639 HUB: Service Inventory Event Subscriptions
    #   POST /tmf-api/serviceInventory/v4/hub
    #   GET  /tmf-api/serviceInventory/v4/hub
    #   DELETE /tmf-api/serviceInventory/v4/hub/{id}
    # =======================================================

    @http.route(
        '/tmf-api/serviceInventory/v4/hub',
        type='jsonrpc', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_service_events(self, **kwargs):
        """
        Example body:
        {
          "callback": "https://my-listener/hook",
          "query": "state=active",
          "eventType": "create",  // create|update|delete|any
          "secret": "token-123"
        }
        """
        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return self._error(400, "Bad Request", "Invalid JSON body")

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        event_type = payload.get("eventType", "any")
        secret = payload.get("secret")

        # Normalize event_type to our selection field
        if event_type not in ['create', 'update', 'delete', 'any']:
            event_type = 'any'

        sub = request.env['tmf.hub.subscription'].sudo().create({
            "name": f"Service-{callback}",
            "api_name": "service",          # matches TMFService.create/write/unlink
            "callback": callback,
            "query": query,
            "event_type": event_type,
            "secret": secret,
        })

        resp = {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query,
            "eventType": sub.event_type,
            "@type": "EventSubscription",
        }
        return resp

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
            "eventType": s.event_type,
            "@type": "EventSubscription",
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
