from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/geographicAddressManagement/v4/GeographicAddress', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.geographic.address'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/geographicAddressManagement/v4/GeographicAddress', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['city', 'country', 'locality', 'name', 'postcode', 'state_or_province', 'street_name', 'street_nr', 'street_nr_last', 'street_nr_last_suffix', 'street_nr_suffix', 'street_suffix', 'street_type', 'geographic_location', 'geographic_sub_address']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.geographic.address'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
