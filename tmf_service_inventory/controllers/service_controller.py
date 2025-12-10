from odoo import http
from odoo.http import request
import json

class TMFServiceController(http.Controller):

    @http.route('/tmf-api/serviceInventory/v4/service', type='http', auth='public', methods=['GET'], csrf=False)
    def get_services(self, **params):
        # Allow filtering by Customer ID (very common use case)
        domain = []
        
        # Example: ?relatedParty.id=123
        # Parsing complex query params in Odoo is manual, so we'll check simple params first
        # Ideally, use a library to parse RSQL or nested params
        
        services = request.env['tmf.service'].sudo().search(domain)
        
        response_data = []
        for s in services:
            response_data.append({
                "id": s.tmf_id,
                "href": s.href,
                "name": s.name,
                "state": s.state,
                "startDate": s.start_date.isoformat() if s.start_date else None,
                "@type": "Service",
                "serviceSpecification": {
                    "id": s.product_specification_id.tmf_id,
                    "name": s.product_specification_id.name
                },
                "relatedParty": [{
                    "id": s.partner_id.tmf_id,
                    "name": s.partner_id.name,
                    "role": "Customer"
                }]
            })

        return request.make_response(
            json.dumps(response_data),
            headers=[('Content-Type', 'application/json')]
        )