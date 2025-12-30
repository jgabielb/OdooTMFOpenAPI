from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class TMFController(http.Controller):

    # 1. LIST
    @http.route('/tmf-api/appointmentManagement/v4/appointment', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.appointment'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    # 2. RETRIEVE ONE
    @http.route('/tmf-api/appointmentManagement/v4/appointment/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resource(self, tmf_id, **params):
        # Search by TMF ID (UUID)
        record = request.env['tmf.appointment'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not record:
             return request.make_response(json.dumps({'code': 404, 'reason': 'Not Found'}), status=404)
             
        return request.make_response(
            json.dumps(record.to_tmf_json()),
            headers=[('Content-Type', 'application/json')]
        )

    # 3. CREATE
    @http.route('/tmf-api/appointmentManagement/v4/appointment', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            
            # 1. Map Simple Fields
            for field in ['category', 'description', 'external_id', 'status', 'note']:
                if field in data:
                    vals[field] = data[field]
            
            # 2. Map & Sanitize Dates (validFor)
            # CTK sends "2018-02-15T16:00:00.000Z", Odoo hates the "Z" and ".000"
            valid_for = data.get('validFor', {})
            if valid_for:
                if 'startDateTime' in valid_for:
                    # Strip 'Z' and milliseconds if present
                    raw_start = valid_for['startDateTime'].replace('Z', '').split('.')[0]
                    vals['valid_for_start'] = raw_start.replace('T', ' ')
                    
                if 'endDateTime' in valid_for:
                    raw_end = valid_for['endDateTime'].replace('Z', '').split('.')[0]
                    vals['valid_for_end'] = raw_end.replace('T', ' ')
            
            # 3. Create
            new_rec = request.env['tmf.appointment'].sudo().create(vals)
            
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                status=201, 
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)

    # 4. PATCH
    @http.route('/tmf-api/appointmentManagement/v4/appointment/<string:tmf_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def update_resource(self, tmf_id, **params):
        try:
            record = request.env['tmf.appointment'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
            if not record:
                return request.make_response(json.dumps({'code': 404, 'reason': 'Not Found'}), status=404)

            data = json.loads(request.httprequest.data)
            vals = {}
            
            for field in ['category', 'description', 'external_id', 'status']:
                if field in data:
                    vals[field] = data[field]

            valid_for = data.get('validFor')
            if isinstance(valid_for, dict):
                if 'startDateTime' in valid_for:
                    vals['valid_for_start'] = valid_for['startDateTime']
                if 'endDateTime' in valid_for:
                    vals['valid_for_end'] = valid_for['endDateTime']

            record.write(vals)
            
            return request.make_response(
                json.dumps(record.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)

    # 5. DELETE
    @http.route('/tmf-api/appointmentManagement/v4/appointment/<string:tmf_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_resource(self, tmf_id, **params):
        record = request.env['tmf.appointment'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if record:
            record.unlink()
        return request.make_response('', status=204)