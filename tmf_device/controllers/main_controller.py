from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/deviceManagement/v4/Device', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        domain = []
        env = request.env['tmf.device'].sudo()
        records = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)
        data = [r.to_tmf_json() for r in records]
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json'), ('X-Total-Count', str(total)), ('X-Result-Count', str(len(data)))]
        )

    @http.route('/tmf-api/deviceManagement/v4/Device', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['alternate_name', 'area_served', 'battery_level', 'category', 'data_provider', 'date_created', 'date_first_used', 'date_installed', 'date_last_calibration', 'date_last_value_reported', 'date_manufactured', 'date_modified', 'description', 'device_state', 'device_type', 'end_date', 'firmware_version', 'hardware_version', 'lifecycle_state', 'manufacture_date', 'mnc', 'name', 'os_version', 'power_state', 'provider', 'serial_number', 'software_version', 'source', 'start_date', 'value', 'version', 'version_number', 'address', 'characteristic', 'configuration', 'location', 'mac_address', 'note', 'party_role', 'place', 'related_party', 'resource_relationship', 'rule']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.device'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
