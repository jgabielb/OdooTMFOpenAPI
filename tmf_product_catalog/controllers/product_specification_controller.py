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

    # -------------------------------------------------------------------------
    # GET (List) and POST (Create)
    # -------------------------------------------------------------------------
    @http.route(
        '/tmf-api/productCatalogManagement/v5/productSpecification',
        type='http', auth='public', methods=['GET', 'POST'], csrf=False
    )
    def product_specification_list_create(self, **params):
        if request.httprequest.method == 'POST':
            return self._create_spec()
        
        return self._list_specs(**params)

    def _list_specs(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        domain = []
        lifecycle = params.get('lifecycleStatus')
        if lifecycle:
            # Map TMF status to Odoo selection if necessary, or check exact match
            # Odoo selection: 'design', 'active', 'retired'
            status_map = {'In Design': 'design', 'Active': 'active', 'Retired': 'retired'}
            mapped_status = status_map.get(lifecycle, lifecycle)
            domain.append(('lifecycle_status', '=', mapped_status))

        specs = request.env['tmf.product.specification'].sudo().search(
            domain, offset=offset, limit=limit, order='id desc'
        )
        data = [s.to_tmf_json() for s in specs]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    def _create_spec(self):
        try:
            data = json.loads(request.httprequest.data)
        except Exception:
            return self._error(400, "Bad Request", "Invalid JSON data")

        # Map TMF fields to Odoo fields
        vals = {
            'name': data.get('name'),
            'description': data.get('description'),
            'brand': data.get('brand'),
            'product_number': data.get('productNumber'),
            'version': data.get('version', '1.0'),
        }

        # Handle Lifecycle Status Mapping (TMF Enum -> Odoo Selection)
        if 'lifecycleStatus' in data:
            status_map = {'In Design': 'design', 'Active': 'active', 'Retired': 'retired'}
            vals['lifecycle_status'] = status_map.get(data['lifecycleStatus'], 'design')

        try:
            new_spec = request.env['tmf.product.specification'].sudo().create(vals)
        except Exception as e:
            return self._error(400, "Creation Error", str(e))

        return request.make_response(
            json.dumps(new_spec.to_tmf_json()),
            headers=[('Content-Type', 'application/json')],
            status=201
        )

    # -------------------------------------------------------------------------
    # GET, PATCH, DELETE (Individual Resource)
    # -------------------------------------------------------------------------
    @http.route(
        '/tmf-api/productCatalogManagement/v5/productSpecification/<string:tmf_id>',
        type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False
    )
    def product_specification_detail(self, tmf_id, **params):
        # 1. Find the record
        spec = request.env['tmf.product.specification'].sudo().search(
            [('tmf_id', '=', tmf_id)], limit=1
        )
        if not spec:
            # Fallback search by ID if tmf_id lookup fails (common in early testing)
            if tmf_id.isdigit():
                 spec = request.env['tmf.product.specification'].sudo().browse(int(tmf_id))
                 if not spec.exists():
                     return self._error(404, "Not Found", f"ProductSpecification {tmf_id} not found")
            else:
                return self._error(404, "Not Found", f"ProductSpecification {tmf_id} not found")

        # 2. Dispatch based on method
        method = request.httprequest.method
        if method == 'GET':
            return self._get_spec(spec)
        elif method == 'PATCH':
            return self._patch_spec(spec)
        elif method == 'DELETE':
            return self._delete_spec(spec)

    def _get_spec(self, spec):
        data = spec.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    def _patch_spec(self, spec):
        try:
            data = json.loads(request.httprequest.data)
        except Exception:
            return self._error(400, "Bad Request", "Invalid JSON")

        vals = {}
        if 'name' in data: vals['name'] = data['name']
        if 'description' in data: vals['description'] = data['description']
        if 'brand' in data: vals['brand'] = data['brand']
        if 'productNumber' in data: vals['product_number'] = data['productNumber']
        if 'version' in data: vals['version'] = data['version']
        
        if 'lifecycleStatus' in data:
             status_map = {'In Design': 'design', 'Active': 'active', 'Retired': 'retired'}
             vals['lifecycle_status'] = status_map.get(data['lifecycleStatus'], 'design')

        if vals:
            try:
                spec.write(vals)
            except Exception as e:
                return self._error(400, "Update Error", str(e))

        return request.make_response(
            json.dumps(spec.to_tmf_json()),
            headers=[('Content-Type', 'application/json')],
            status=200
        )

    def _delete_spec(self, spec):
        try:
            spec.unlink()
        except Exception as e:
            return self._error(400, "Delete Error", str(e))
            
        return request.make_response('', status=204)