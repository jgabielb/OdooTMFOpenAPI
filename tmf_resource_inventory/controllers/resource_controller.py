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

    @http.route(
        '/tmf-api/resourceInventory/v4/resource',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_resources(self, **params):
        domain = []

        # Pagination
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        # Simple filters (expand as you like)
        # ?serialNumber=XYZ
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
