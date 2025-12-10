from odoo import http
from odoo.http import request
import json

class TMFResourceController(http.Controller):

    @http.route('/tmf-api/resourceInventory/v4/resource', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        resources = request.env['stock.lot'].sudo().search([])
        
        response_data = []
        for r in resources:
            response_data.append({
                "id": r.tmf_id,
                "href": r.href,
                "name": r.name, # The Serial Number
                "resourceStatus": r.resource_status,
                "@type": "PhysicalResource",
                "serialNumber": r.name,
                "note": [{
                    "text": f"Linked Product: {r.product_id.name}"
                }]
            })

        return request.make_response(
            json.dumps(response_data),
            headers=[('Content-Type', 'application/json')]
        )