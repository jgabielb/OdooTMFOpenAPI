from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):

    @http.route('/tmf-api/partyPrivacyAgreementManagement/v4/PartyPrivacyAgreement', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.party.privacy.agreement'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json() for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/tmf-api/partyPrivacyAgreementManagement/v4/PartyPrivacyAgreement', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            # Basic field mapping
            for field in ['agreement_type', 'description', 'document_number', 'initial_date', 'name', 'statement_of_intent', 'status', 'version', 'agreement_authorization', 'agreement_item', 'agreement_period', 'agreement_specification', 'associated_agreement', 'characteristic', 'completion_date', 'engaged_party', 'party_privacy_profile', 'party_privacy_profile_characteristic']:
                if field in data:
                    vals[field] = data[field]
            
            new_rec = request.env['tmf.party.privacy.agreement'].sudo().create(vals)
            return request.make_response(
                json.dumps(new_rec.to_tmf_json()),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(json.dumps({'error': str(e)}), status=400)
