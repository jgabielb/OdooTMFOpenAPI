from odoo import http
from odoo.http import request
import json


class TMFPartyController(http.Controller):

    # ---------- Error helper ----------

    def _error(self, status, reason, message):
        body = json.dumps({
            "code": str(status),
            "reason": reason,
            "message": message,
        })
        return request.make_response(
            body,
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    # =======================================================
    # INDIVIDUALS (TMF632)
    # =======================================================

    @http.route(
        '/tmf-api/party/v4/individual',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_individuals(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        domain = [('is_company', '=', False)]

        # Simple filter: ?givenName=...
        given_name = params.get('givenName')
        if given_name:
            domain.append(('name', 'ilike', given_name))

        individuals = request.env['res.partner'].sudo().search(
            domain, offset=offset, limit=limit, order='id desc'
        )
        data = [p.to_tmf_json() for p in individuals]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/party/v4/individual/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_individual(self, tmf_id, **params):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1
        )
        if not partner:
            return self._error(404, "Not Found", f"Individual {tmf_id} not found")

        data = partner.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/party/v4/individual',
        type='jsonrpc', auth='public', methods=['POST'], csrf=False
    )
    def create_individual(self, **kwargs):
        # Parse raw JSON body
        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return self._error(400, "Bad Request", "Invalid JSON body")

        given_name = payload.get('givenName') or payload.get('name')
        if not given_name:
            return self._error(400, "Bad Request", "givenName (or name) is required")

        vals = {
            'name': given_name,
            'is_company': False,
            'tmf_customer_type': 'individual',
        }

        contact_medium = payload.get('contactMedium') or []
        for cm in contact_medium:
            if cm.get('mediumType') == 'email':
                characteristic = cm.get('characteristic') or {}
                email = characteristic.get('emailAddress')
                if email:
                    vals['email'] = email
                    break

        partner = request.env['res.partner'].sudo().create(vals)

        # ---- NOTIFICAR HUB ----
        request.env['tmf.hub.subscription'].sudo()._notify_subscribers(
            api_name='party',
            event_type='create',
            resource_json={
                "resourceType": "individual",
                "resource": partner.to_tmf_json(),
            },
        )

        return partner.to_tmf_json()

    @http.route(
        '/tmf-api/party/v4/individual/<string:tmf_id>',
        type='jsonrpc', auth='public', methods=['PATCH'], csrf=False
    )
    def patch_individual(self, tmf_id, **kwargs):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1
        )
        if not partner:
            return self._error(404, "Not Found", f"Individual {tmf_id} not found")

        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return self._error(400, "Bad Request", "Invalid JSON body")
        vals = {}

        if 'givenName' in payload:
            vals['name'] = payload['givenName']
        if 'name' in payload and not vals.get('name'):
            vals['name'] = payload['name']

        if 'contactMedium' in payload:
            cm_list = payload['contactMedium'] or []
            for cm in cm_list:
                if cm.get('mediumType') == 'email':
                    characteristic = cm.get('characteristic') or {}
                    email = characteristic.get('emailAddress')
                    if email:
                        vals['email'] = email
                        break

        if vals:
            partner.sudo().write(vals)

        # ---- NOTIFICAR HUB ----
        request.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                api_name='party',
                event_type='update',
                resource_json={
                    "resourceType": "individual",
                    "resource": partner.to_tmf_json(),
                },
            )

        return partner.to_tmf_json()

    @http.route(
        '/tmf-api/party/v4/individual/<string:tmf_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def delete_individual(self, tmf_id, **kwargs):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1
        )
        if not partner:
            return self._error(404, "Not Found", f"Individual {tmf_id} not found")
        
        payload = {
            "resourceType": "individual",
            "resource": partner.to_tmf_json(),
        }

        partner.unlink()

        # --- NOTIFICAR HUB ---
        request.env['tmf.hub.subscription'].sudo()._notify_subscribers(
            api_name='party',
            event_type='delete',
            resource_json=payload,
        )

        return request.make_response('', status=204)

    # =======================================================
    # ORGANIZATIONS (TMF632)
    # =======================================================

    @http.route(
        '/tmf-api/party/v4/organization',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_organizations(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 50))

        domain = [('is_company', '=', True)]

        # Simple filter: ?name=...
        name_filter = params.get('name')
        if name_filter:
            domain.append(('name', 'ilike', name_filter))

        orgs = request.env['res.partner'].sudo().search(
            domain, offset=offset, limit=limit, order='id desc'
        )
        data = [p.to_tmf_json() for p in orgs]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/party/v4/organization/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_organization(self, tmf_id, **params):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1
        )
        if not partner:
            return self._error(404, "Not Found", f"Organization {tmf_id} not found")

        data = partner.to_tmf_json()
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/party/v4/organization',
        type='jsonrpc', auth='public', methods=['POST'], csrf=False
    )
    def create_organization(self, **kwargs):
        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return self._error(400, "Bad Request", "Invalid JSON body")

        name = payload.get('name')
        if not name:
            return self._error(400, "Bad Request", "name is required")

        vals = {
            'name': name,
            'is_company': True,
            'tmf_customer_type': 'organization',
        }

        contact_medium = payload.get('contactMedium') or []
        for cm in contact_medium:
            if cm.get('mediumType') == 'email':
                characteristic = cm.get('characteristic') or {}
                email = characteristic.get('emailAddress')
                if email:
                    vals['email'] = email
                    break

        partner = request.env['res.partner'].sudo().create(vals)

        # ---- NOTIFICAR HUB ----
        resource_json = {
            "resource": partner.to_tmf_json(),
            "eventType": "organizationCreateEvent",
        }
        request.env['tmf.hub.subscription'].sudo()._notify_subscribers(
            api_name='party',
            event_type='create',
            resource_json={
                "resourceType": "organization",
                "resource": partner.to_tmf_json(),
            },
        )

        return partner.to_tmf_json()

    @http.route(
        '/tmf-api/party/v4/organization/<string:tmf_id>',
        type='jsonrpc', auth='public', methods=['PATCH'], csrf=False
    )
    def patch_organization(self, tmf_id, **kwargs):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1
        )
        if not partner:
            return self._error(404, "Not Found", f"Organization {tmf_id} not found")

        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return self._error(400, "Bad Request", "Invalid JSON body")
        vals = {}

        if 'name' in payload:
            vals['name'] = payload['name']

        if 'contactMedium' in payload:
            cm_list = payload['contactMedium'] or []
            for cm in cm_list:
                if cm.get('mediumType') == 'email':
                    characteristic = cm.get('characteristic') or {}
                    email = characteristic.get('emailAddress')
                    if email:
                        vals['email'] = email
                        break

        if vals:
            partner.sudo().write(vals)

        # ---- NOTIFICAR HUB ----
        request.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                api_name='party',
                event_type='update',
                resource_json={
                    "resourceType": "organization",
                    "resource": partner.to_tmf_json(),
                },
            )

        return partner.to_tmf_json()

    @http.route(
        '/tmf-api/party/v4/organization/<string:tmf_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def delete_organization(self, tmf_id, **kwargs):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1
        )
        if not partner:
            return self._error(404, "Not Found", f"Organization {tmf_id} not found")

        payload = {
            "resourceType": "organization",
            "resource": partner.to_tmf_json(),
        }

        partner.unlink()

        request.env['tmf.hub.subscription'].sudo()._notify_subscribers(
            api_name='party',
            event_type='delete',
            resource_json=payload,
        )

        return request.make_response('', status=204)

    # =======================================================
    # HUB: Party Event Subscriptions (Individual + Organization)
    # =======================================================
    @http.route(
        '/tmf-api/party/v4/hub',
        type='jsonrpc', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_party_events(self, **kwargs):
        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return self._error(400, "Bad Request", "Invalid JSON body")

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        event_type = payload.get("eventType", "any")  # opcional en el payload

        sub = request.env['tmf.hub.subscription'].sudo().create({
            "name": f"Party Hub subscription - {callback}",
            "api_name": "party",
            "callback": callback,
            "query": query,
            "event_type": event_type if event_type in ("create", "update", "delete", "any") else "any",
        })

        return {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query,
            "@type": "EventSubscription",
        }

    @http.route(
        '/tmf-api/party/v4/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_party_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'party')
        ])
        data = [{
            "id": str(s.id),
            "callback": s.callback,
            "query": s.query,
            "@type": "EventSubscription",
        } for s in subs]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        '/tmf-api/party/v4/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_party_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
