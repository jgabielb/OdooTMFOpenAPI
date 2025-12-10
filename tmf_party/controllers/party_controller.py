# tmf_party/controllers/party_controller.py
from odoo import http, fields
from odoo.http import request
import json

class TMFPartyController(http.Controller):

    @http.route('/tmf-api/party/v4/individual', type='http', auth='public', methods=['GET'], csrf=False)
    def get_individuals(self, **params):
        """
        TMF632: List Individuals
        Maps Odoo Partners (is_company=False) to TMF JSON.
        """
        # 1. Filter: specific TMF logic (Only individuals)
        domain = [('is_company', '=', False)]
        
        # 2. Add limits/offsets (Pagination) - optional for now
        limit = int(params.get('limit', 10))
        
        # 3. Search Odoo
        # sudo() is used here for 'public' auth to work for testing. 
        # In production, use auth='user' and proper ACLs.
        partners = request.env['res.partner'].sudo().search(domain, limit=limit)
        
        # 4. Serialize (Convert Python Objects to JSON)
        response_data = []
        for p in partners:
            # Basic TMF Mapping
            party_json = {
                "id": p.tmf_id or str(p.id),
                "href": p.href,
                "name": p.name,
                "status": p.tmf_status,
                "contactMedium": [],
                "@type": "Individual"
            }
            
            # Map Email
            if p.email:
                party_json["contactMedium"].append({
                    "mediumType": "email",
                    "characteristic": {
                        "emailAddress": p.email
                    }
                })
                
            # Map Phone
            if p.phone:
                party_json["contactMedium"].append({
                    "mediumType": "phone",
                    "characteristic": {
                        "phoneNumber": p.phone
                    }
                })

            response_data.append(party_json)

        # 5. Return JSON Response
        return request.make_response(
            json.dumps(response_data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/party/v4/individual/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_individual_by_id(self, tmf_id, **params):
        """
        TMF632: Get Individual by ID
        """
        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        
        if not partner:
            error = {"code": "404", "reason": "Not Found", "message": f"Party with ID {tmf_id} not found."}
            return request.make_response(json.dumps(error), status=404, headers=[('Content-Type', 'application/json')])

        # Reuse serialization logic (Simplified for demo)
        data = {
            "id": partner.tmf_id,
            "name": partner.name,
            "status": partner.tmf_status,
            "@type": "Individual"
        }
        
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )