from odoo import http
from odoo.http import request
import json


class TMFProductSpecificationController(http.Controller):

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
        '/tmf-api/productCatalogManagement/v4/productSpecification',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_specs(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        domain = []
        lifecycle = params.get('lifecycleStatus')
        if lifecycle:
            # map 'In Design'/'Active'/'Retired' if you want, or expect 'design/active/retired'
            domain.append(('lifecycle_status', '=', lifecycle))

        specs = request.env['product.specification'].sudo().search(
            domain, offset=offset, limit=limit, order='id desc'
        )
        data = [s.to_tmf_json() for s in specs]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/productCatalogManagement/v4/productSpecification/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_spec(self, tmf_id, **params):
        spec = request.env['product.specification'].sudo().search(
            [('tmf_id', '=', tmf_id)], limit=1
        )
        if not spec:
            return self._error(404, "Not Found", f"ProductSpecification {tmf_id} not found")

        data = spec.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )
