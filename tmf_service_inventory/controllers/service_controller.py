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
            # first try tmf_id; if it fails, fall back to numeric id
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
