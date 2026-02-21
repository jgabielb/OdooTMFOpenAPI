from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/managedEntityManagement/v4/ManagedEntity', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.managed.entity'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/managedEntityManagement/v4/ManagedEntity', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['context', 'description', 'valid_for', 'is_bundle', 'is_external', 'name', 'last_update', 'lifecycle_status', 'status_change_date', 'version', 'attachment', 'characteristic', 'entity_relationship', 'entity_specification', 'note', 'related_party']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.managed.entity'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
