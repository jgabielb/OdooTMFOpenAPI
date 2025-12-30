from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/resourceFunctionManagement/v4/ResourceFunction', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.resource.function'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/resourceFunctionManagement/v4/ResourceFunction', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['category', 'description', 'end_operating_date', 'function_type', 'name', 'priority', 'resource_version', 'role', 'start_operating_date', 'value', 'activation_feature', 'administrative_state', 'attachment', 'auto_modification', 'connection_point', 'connectivity', 'note', 'operational_state', 'place', 'related_party', 'resource_characteristic', 'resource_relationship', 'resource_specification', 'resource_status', 'schedule', 'usage_state']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.resource.function'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
