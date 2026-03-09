from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/aiContractSpecificationManagement/v4/AiContractSpecification', type='http', auth='public', methods=['GET'], csrf=False)
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
        env = request.env['tmf.ai.contract.specification'].sudo()
        records = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)
        data = [r.to_tmf_json() for r in records]
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json'), ('X-Total-Count', str(total)), ('X-Result-Count', str(len(data)))]
        )

    @http.route('/tmf-api/aiContractSpecificationManagement/v4/AiContractSpecification', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['description', 'is_bundle', 'last_update', 'lifecycle_status', 'name', 'version', 'attachment', 'constraint', 'entity_spec_relationship', 'related_party', 'spec_characteristic', 'target_entity_schema', 'valid_for']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.ai.contract.specification'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
