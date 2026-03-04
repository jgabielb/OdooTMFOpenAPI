from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class TMFController(http.Controller):
    @staticmethod
    def _normalize_dt(raw):
        if not raw:
            return False
        text = str(raw).strip().replace("Z", "")
        if "." in text:
            text = text.split(".", 1)[0]
        return text.replace("T", " ")

    # 1. LIST
    @http.route(
        ['/tmf-api/appointmentManagement/v4/appointment', '/tmf-api/appointment/v4/appointment'],
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_resources(self, **params):
        records = request.env['tmf.appointment'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    # 2. RETRIEVE ONE
    @http.route(
        ['/tmf-api/appointmentManagement/v4/appointment/<string:tmf_id>', '/tmf-api/appointment/v4/appointment/<string:tmf_id>'],
        type='http', auth='public', methods=['GET'], csrf=False
    )
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
    @http.route(
        ['/tmf-api/appointmentManagement/v4/appointment', '/tmf-api/appointment/v4/appointment'],
        type='http', auth='public', methods=['POST'], csrf=False
    )
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            
            # 1. Map Simple Fields
            for src, dst in [('category', 'category'), ('description', 'description'), ('status', 'status'), ('note', 'note')]:
                if src in data:
                    vals[dst] = data[src]
            if 'externalId' in data:
                vals['external_id'] = data['externalId']
            elif 'external_id' in data:
                vals['external_id'] = data['external_id']
            if 'relatedParty' in data:
                vals['related_party'] = json.dumps(data.get('relatedParty'), ensure_ascii=False)
            
            # 2. Map & Sanitize Dates (validFor)
            # CTK sends "2018-02-15T16:00:00.000Z", Odoo hates the "Z" and ".000"
            valid_for = data.get('validFor', {})
            if valid_for:
                if 'startDateTime' in valid_for:
                    vals['valid_for_start'] = self._normalize_dt(valid_for['startDateTime'])
                    
                if 'endDateTime' in valid_for:
                    vals['valid_for_end'] = self._normalize_dt(valid_for['endDateTime'])
            
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
    @http.route(
        ['/tmf-api/appointmentManagement/v4/appointment/<string:tmf_id>', '/tmf-api/appointment/v4/appointment/<string:tmf_id>'],
        type='http', auth='public', methods=['PATCH'], csrf=False
    )
    def update_resource(self, tmf_id, **params):
        try:
            record = request.env['tmf.appointment'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
            if not record:
                return request.make_response(json.dumps({'code': 404, 'reason': 'Not Found'}), status=404)

            data = json.loads(request.httprequest.data)
            vals = {}
            
            for src, dst in [('category', 'category'), ('description', 'description'), ('status', 'status')]:
                if src in data:
                    vals[dst] = data[src]
            if 'externalId' in data:
                vals['external_id'] = data['externalId']
            elif 'external_id' in data:
                vals['external_id'] = data['external_id']
            if 'relatedParty' in data:
                vals['related_party'] = json.dumps(data.get('relatedParty'), ensure_ascii=False)

            valid_for = data.get('validFor')
            if isinstance(valid_for, dict):
                if 'startDateTime' in valid_for:
                    vals['valid_for_start'] = self._normalize_dt(valid_for['startDateTime'])
                if 'endDateTime' in valid_for:
                    vals['valid_for_end'] = self._normalize_dt(valid_for['endDateTime'])

            record.write(vals)
            
            return request.make_response(
                json.dumps(record.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)

    # 5. DELETE
    @http.route(
        ['/tmf-api/appointmentManagement/v4/appointment/<string:tmf_id>', '/tmf-api/appointment/v4/appointment/<string:tmf_id>'],
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def delete_resource(self, tmf_id, **params):
        record = request.env['tmf.appointment'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if record:
            record.unlink()
        return request.make_response('', status=204)
