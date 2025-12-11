from odoo import http
from odoo.http import request
import json


class TMFResourceController(http.Controller):

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
    # RESOURCE INVENTORY – QUERY
    # =======================================================
    @http.route(
        '/tmf-api/resourceInventory/v4/resource',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_resources(self, **params):
        domain = []

        # Pagination
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        # ?serialNumber=XYZ  → usamos name como serialNumber
        serial_number = params.get('serialNumber')
        if serial_number:
            domain.append(('name', '=', serial_number))

        # ?resourceStatus=installed / available / ...
        resource_status = params.get('resourceStatus')
        if resource_status:
            domain.append(('resource_status', '=', resource_status))

        # ?product.id=123 (product id or tmf_id)
        product_id_param = params.get('product.id')
        if product_id_param:
            domain += ['|',
                       ('product_id.tmf_id', '=', product_id_param),
                       ('product_id', '=', int(product_id_param)) if product_id_param.isdigit() else ('id', '=', 0)
                      ]

        resources = request.env['stock.lot'].sudo().search(
            domain, offset=offset, limit=limit
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

    # =======================================================
    # HUB – RESOURCE INVENTORY EVENT SUBSCRIPTIONS
    # =======================================================
    @http.route(
        '/tmf-api/resourceInventory/v4/hub',
        type='jsonrpc', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_resource_inventory_events(self, **kwargs):
        """
        Crea una suscripción para eventos de Resource Inventory.
        body ej:
        {
          "callback": "https://mi.listener/hook",
          "query": "resourceStatus=installed",
          "eventType": "any" | "create" | "update" | "delete",
          "secret": "opcional"
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

        if event_type not in ['create', 'update', 'delete', 'any']:
            event_type = 'any'

        sub = request.env['tmf.hub.subscription'].sudo().create({
            "name": f"ResourceInventory-{callback}",
            "api_name": "resourceInventory",
            "callback": callback,
            "query": query,
            "event_type": event_type,
            "secret": secret,
        })

        return {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query,
            "eventType": sub.event_type,
            "@type": "EventSubscription",
        }

    @http.route(
        '/tmf-api/resourceInventory/v4/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_resource_inventory_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'resourceInventory')
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
        '/tmf-api/resourceInventory/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_resource_inventory_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
