from odoo import http
from odoo.http import request
from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController
import logging

_logger = logging.getLogger(__name__)

TMF_BASE = "/tmf-api/partyManagement/v5"


class TMFPartyController(TMFBaseController):
    """TMF632 Party API (v5) - Individual, Organization and Hub."""

    # -----------------------
    # Helpers
    # -----------------------

    def _partner_domain_for_individual(self, params):
        domain = [('is_company', '=', False), ('tmf_managed', '=', True)]
        if params.get('givenName'):
            domain.append(('tmf_given_name', 'ilike', params['givenName']))
        if params.get('familyName'):
            domain.append(('tmf_family_name', 'ilike', params['familyName']))
        if params.get('status'):
            domain.append(('tmf_status', '=', params['status']))

        # Document-based filters (HTTP-only verification support)
        if params.get('documentNumber'):
            domain.append(('tmf_document_number', '=', str(params['documentNumber']).strip()))
        if params.get('documentType'):
            domain.append(('tmf_document_type', '=', str(params['documentType']).strip()))

        return domain

    def _partner_domain_for_org(self, params):
        domain = [('is_company', '=', True), ('tmf_managed', '=', True)]
        if params.get('name'):
            domain.append(('name', 'ilike', params['name']))
        if params.get('status'):
            domain.append(('tmf_status', '=', params['status']))

        # Document-based filters (HTTP-only verification support)
        if params.get('documentNumber'):
            domain.append(('tmf_document_number', '=', str(params['documentNumber']).strip()))
        if params.get('documentType'):
            domain.append(('tmf_document_type', '=', str(params['documentType']).strip()))

        return domain

    def _find_individual(self, tmf_id):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1
        )
        if not partner and tmf_id.isdigit():
            partner = request.env['res.partner'].sudo().browse(int(tmf_id))
            if not partner.exists() or partner.is_company:
                return request.env['res.partner'].sudo()
        return partner

    def _find_organization(self, tmf_id):
        partner = request.env['res.partner'].sudo().search(
            [('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1
        )
        if not partner and tmf_id.isdigit():
            partner = request.env['res.partner'].sudo().browse(int(tmf_id))
            if not partner.exists() or not partner.is_company:
                return request.env['res.partner'].sudo()
        return partner

    # -----------------------
    # Individual
    # -----------------------

    @http.route(f'{TMF_BASE}/individual', type='http', auth='public', methods=['GET'], csrf=False)
    def list_individuals(self, **kwargs):
        domain = self._partner_domain_for_individual(kwargs)
        return self._list_response('res.partner', domain, lambda p: p.to_tmf_json(), kwargs)

    @http.route(f'{TMF_BASE}/individual', type='http', auth='public', methods=['POST'], csrf=False)
    def create_individual(self, **kwargs):
        payload = self._parse_json_body()

        if payload.get('@type') and payload.get('@type') != 'Individual':
            return self._error(400, "Bad Request", "@type must be 'Individual' for this endpoint")

        if not payload.get('givenName') or not payload.get('familyName'):
            return self._error(400, "Bad Request", "Missing mandatory fields: givenName, familyName, @type")

        if payload.get('@type') is None:
            return self._error(400, "Bad Request", "Missing mandatory field: @type")

        Partner = request.env['res.partner'].sudo()

        # Extract email from contactMedium (TMF632 v5 shape: characteristic.emailAddress)
        email = ""
        for medium in (payload.get('contactMedium') or []):
            if (medium.get('mediumType') or '').lower() == 'email':
                ch = medium.get('characteristic') or {}
                email = (ch.get('emailAddress') or ch.get('email') or '').strip().lower()
                if email:
                    break

        # Document-based matching (user preference: document is the primary key)
        doc = payload.get('document') if isinstance(payload.get('document'), dict) else {}
        doc_number = (doc.get('number') or doc.get('documentNumber') or '').strip()
        doc_type = (doc.get('type') or doc.get('documentType') or '').strip()

        partner = Partner
        if doc_number:
            dom = [('tmf_document_number', '=', doc_number), ('is_company', '=', False)]
            if doc_type:
                dom.append(('tmf_document_type', '=', doc_type))
            _logger.info("TMF632 create_individual document match: dom=%s", dom)
            partner = Partner.search(dom, limit=1)
            _logger.info("TMF632 create_individual document match: found=%s", partner.id if partner else None)

        # Duplicate-email guard: if no document is provided AND the email is
        # already present on a different individual partner, reject with 422.
        # When a document IS provided, document-match wins (same person re-creating).
        if email and not partner:
            existing = Partner.search([
                ('email', '=ilike', email),
                ('is_company', '=', False),
            ], limit=1)
            if existing:
                return self._error(
                    422, "DUPLICATE_PARTY",
                    f"An individual with email '{email}' already exists",
                )

        vals = {
            'is_company': False,
            'tmf_managed': True,
            'tmf_given_name': payload.get('givenName'),
            'tmf_family_name': payload.get('familyName'),
            'name': f"{payload.get('givenName')} {payload.get('familyName')}",
            'tmf_status': payload.get('status') or 'initialized',
        }
        if doc_number:
            vals['tmf_document_number'] = doc_number
        if doc_type:
            vals['tmf_document_type'] = doc_type
        if email:
            vals['email'] = email

        if partner and partner.exists():
            # Reuse existing CRM contact by document
            partner.write(vals)
        else:
            partner = Partner.create(vals)
        body = partner.to_tmf_json()
        return self._json(body, status=201, headers=[('Location', body.get('href', ''))])

    @http.route(f'{TMF_BASE}/individual/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_individual(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        partner = self._find_individual(tmf_id)
        if not partner:
            return self._error(404, "Not Found", f"Individual {tmf_id} not found")
        return self._json(self._select_fields(partner.to_tmf_json(), kwargs.get('fields')))

    @http.route(f'{TMF_BASE}/individual/<string:tmf_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_individual(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        ctype = (request.httprequest.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if ctype not in {'application/merge-patch+json', 'application/json'}:
            return self._error(415, "Unsupported Media Type", "Use Content-Type: application/merge-patch+json (or application/json)")

        payload = self._parse_json_body()
        partner = self._find_individual(tmf_id)
        if not partner:
            return self._error(404, "Not Found", f"Individual {tmf_id} not found")

        if payload.get('@type') and payload.get('@type') != 'Individual':
            return self._error(400, "Bad Request", "@type must be 'Individual'")

        vals = {}
        if 'givenName' in payload:
            vals['tmf_given_name'] = payload.get('givenName')
        if 'familyName' in payload:
            vals['tmf_family_name'] = payload.get('familyName')
        if 'status' in payload:
            vals['tmf_status'] = payload.get('status')

        if 'tmf_given_name' in vals or 'tmf_family_name' in vals:
            g = vals.get('tmf_given_name', partner.tmf_given_name or '')
            f = vals.get('tmf_family_name', partner.tmf_family_name or '')
            vals['name'] = (f"{g} {f}").strip()

        if vals:
            partner.write(vals)

        return self._json(partner.to_tmf_json())

    @http.route(
        [
            f'{TMF_BASE}/individual',
            f'{TMF_BASE}/individual/',
            f'{TMF_BASE}/individual/<string:tmf_id>',
            f'{TMF_BASE}/individual/<string:tmf_id>/',
            f'{TMF_BASE}/individual/<path:tmf_id>',
            f'{TMF_BASE}/individual/<path:tmf_id>/',
        ],
        type='http', auth='public', methods=['DELETE'], csrf=False,
    )
    def delete_individual(self, tmf_id=None, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id or kwargs.get('id') or '')
        if "/" in tmf_id:
            tmf_id = tmf_id.split("/", 1)[0].strip()
        partner = self._find_individual(tmf_id)
        if not partner:
            # Idempotent: if already gone, return 204
            return request.make_response('', status=204)
        try:
            with request.env.cr.savepoint():
                partner.with_context(skip_tmf_bridge=True).unlink()
        except Exception as e:
            err = str(e).lower()
            if "foreign key constraint" in err or "violates" in err or "integrity" in err:
                return self._error(409, "Conflict",
                    f"Individual {tmf_id} cannot be deleted: referenced by other resources")
            raise
        return request.make_response('', status=204)

    # -----------------------
    # Organization
    # -----------------------

    @http.route(f'{TMF_BASE}/organization', type='http', auth='public', methods=['GET'], csrf=False)
    def list_organizations(self, **kwargs):
        domain = self._partner_domain_for_org(kwargs)
        return self._list_response('res.partner', domain, lambda p: p.to_tmf_json(), kwargs)

    @http.route(f'{TMF_BASE}/organization', type='http', auth='public', methods=['POST'], csrf=False)
    def create_organization(self, **kwargs):
        payload = self._parse_json_body()

        if payload.get('@type') and payload.get('@type') != 'Organization':
            return self._error(400, "Bad Request", "@type must be 'Organization' for this endpoint")

        if payload.get('@type') is None:
            return self._error(400, "Bad Request", "Missing mandatory field: @type")

        if not payload.get('name'):
            return self._error(400, "Bad Request", "Missing mandatory field: name")

        Partner = request.env['res.partner'].sudo()

        # Document-based matching (optional for organizations too)
        doc = payload.get('document') if isinstance(payload.get('document'), dict) else {}
        doc_number = (doc.get('number') or doc.get('documentNumber') or '').strip()
        doc_type = (doc.get('type') or doc.get('documentType') or '').strip()

        partner = Partner
        if doc_number:
            dom = [('tmf_document_number', '=', doc_number), ('is_company', '=', True)]
            if doc_type:
                dom.append(('tmf_document_type', '=', doc_type))
            _logger.info("TMF632 create_organization document match: dom=%s", dom)
            partner = Partner.search(dom, limit=1)
            _logger.info("TMF632 create_organization document match: found=%s", partner.id if partner else None)

        vals = {
            'is_company': True,
            'tmf_managed': True,
            'name': payload.get('name'),
            'tmf_status': payload.get('status') or 'initialized',
        }
        if doc_number:
            vals['tmf_document_number'] = doc_number
        if doc_type:
            vals['tmf_document_type'] = doc_type

        if partner and partner.exists():
            partner.write(vals)
        else:
            partner = Partner.create(vals)
        body = partner.to_tmf_json()
        return self._json(body, status=201, headers=[('Location', body.get('href', ''))])

    @http.route(f'{TMF_BASE}/organization/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_organization(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        partner = self._find_organization(tmf_id)
        if not partner:
            return self._error(404, "Not Found", f"Organization {tmf_id} not found")
        return self._json(self._select_fields(partner.to_tmf_json(), kwargs.get('fields')))

    @http.route(f'{TMF_BASE}/organization/<string:tmf_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_organization(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        ctype = (request.httprequest.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if ctype not in {'application/merge-patch+json', 'application/json'}:
            return self._error(415, "Unsupported Media Type", "Use Content-Type: application/merge-patch+json (or application/json)")

        payload = self._parse_json_body()
        partner = self._find_organization(tmf_id)
        if not partner:
            return self._error(404, "Not Found", f"Organization {tmf_id} not found")

        if payload.get('@type') and payload.get('@type') != 'Organization':
            return self._error(400, "Bad Request", "@type must be 'Organization'")

        vals = {}
        if 'name' in payload:
            vals['name'] = payload.get('name')
        if 'status' in payload:
            vals['tmf_status'] = payload.get('status')

        if vals:
            partner.write(vals)

        return self._json(partner.to_tmf_json())

    @http.route(
        [
            f'{TMF_BASE}/organization',
            f'{TMF_BASE}/organization/',
            f'{TMF_BASE}/organization/<string:tmf_id>',
            f'{TMF_BASE}/organization/<string:tmf_id>/',
            f'{TMF_BASE}/organization/<path:tmf_id>',
            f'{TMF_BASE}/organization/<path:tmf_id>/',
        ],
        type='http', auth='public', methods=['DELETE'], csrf=False,
    )
    def delete_organization(self, tmf_id=None, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id or kwargs.get('id') or '')
        if "/" in tmf_id:
            tmf_id = tmf_id.split("/", 1)[0].strip()
        partner = self._find_organization(tmf_id)
        if not partner:
            # Idempotent: if already gone, return 204
            return request.make_response('', status=204)
        try:
            with request.env.cr.savepoint():
                partner.with_context(skip_tmf_bridge=True).unlink()
        except Exception as e:
            err = str(e).lower()
            if "foreign key constraint" in err or "violates" in err or "integrity" in err:
                return self._error(409, "Conflict",
                    f"Organization {tmf_id} cannot be deleted: referenced by other resources")
            raise
        return request.make_response('', status=204)

    # -----------------------
    # Hub
    # -----------------------

    def _listener_ok(self):
        payload = self._parse_json_body()
        if not isinstance(payload, dict):
            return self._error(400, "Bad Request", "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f'{TMF_BASE}/hub', type='http', auth='public', methods=['POST'], csrf=False)
    def subscribe_party_events(self, **kwargs):
        payload = self._parse_json_body()
        callback = payload.get('callback')
        query = payload.get('query')

        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory field: callback")

        subs = request.env['tmf.hub.subscription'].sudo().create({
            'name': f"tmf632-party-{callback}",
            'api_name': 'party',
            'callback': callback,
            'query': query or '',
            'event_type': 'any',
            'content_type': 'application/json',
        })

        body = {
            "id": str(subs.id),
            "callback": subs.callback,
            "query": subs.query or "",
        }
        location = f"{TMF_BASE}/hub/{subs.id}"
        return self._json(body, status=201, headers=[('Location', location)])

    @http.route(f'{TMF_BASE}/hub/<string:sub_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def unsubscribe_party_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id)) if sub_id.isdigit() else request.env['tmf.hub.subscription']
        if not subs or not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")
        subs.unlink()
        return request.make_response('', status=204)

    @http.route(f'{TMF_BASE}/<path:subpath>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_party_path_fallback(self, subpath, **kwargs):
        raw = self._normalize_tmf_id(subpath or "")
        base = raw.split("?", 1)[0].strip("/")
        if base.startswith("organization") or base.startswith("individual"):
            return request.make_response('', status=204)
        return self._error(404, "Not Found", f"Resource {subpath} not found")

    @http.route(f'{TMF_BASE}/listener/individualCreateEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_individual_create(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/individualAttributeValueChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_individual_attr(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/individualStateChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_individual_state(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/individualDeleteEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_individual_delete(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/organizationCreateEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_org_create(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/organizationAttributeValueChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_org_attr(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/organizationStateChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_org_state(self, **kwargs):
        return self._listener_ok()

    @http.route(f'{TMF_BASE}/listener/organizationDeleteEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_org_delete(self, **kwargs):
        return self._listener_ok()
