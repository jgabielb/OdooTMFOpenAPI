from odoo import http
from odoo.http import request
import json
from urllib.parse import unquote

TMF_BASE = "/tmf-api/partyManagement/v5"


class TMFPartyController(http.Controller):
    """TMF632 Party API (v5) - minimal implementation for Individual, Organization and Hub."""

    # -----------------------
    # Helpers
    # -----------------------

    def _json(self, payload, status=200, headers=None):
        headers = headers or []
        headers = list(headers) + [('Content-Type', 'application/json')]
        return request.make_response(json.dumps(payload), status=status, headers=headers)

    def _error(self, status, reason, message):
        return self._json(
            {"code": str(status), "reason": reason, "message": message},
            status=status
        )

    def _parse_json_body(self):
        raw = request.httprequest.get_data(cache=False, as_text=False) or b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            # Also accept empty body
            if raw.strip() in (b"", b"{}"):
                return {}
            raise

    def _select_fields(self, obj, fields_param):
        """Apply TMF 'fields' selection (first-level), but always keep required keys.

        CTK expects '@type' (and typically 'id'/'href') even when not requested.
        """
        if not fields_param:
            return obj
        wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
        if not wanted:
            return obj

        required = {'@type', 'id', 'href'}
        wanted_set = set(wanted) | required

        return {k: v for k, v in obj.items() if k in wanted_set}

    def _normalize_tmf_id(self, tmf_id):
        value = unquote((tmf_id or "").strip())
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1].strip()
        return value

    def _partner_domain_for_individual(self, params):
        domain = [('is_company', '=', False), ('tmf_managed', '=', True)]
        if params.get('givenName'):
            domain.append(('tmf_given_name', 'ilike', params['givenName']))
        if params.get('familyName'):
            domain.append(('tmf_family_name', 'ilike', params['familyName']))
        if params.get('status'):
            domain.append(('tmf_status', '=', params['status']))
        return domain

    def _partner_domain_for_org(self, params):
        domain = [('is_company', '=', True), ('tmf_managed', '=', True)]
        if params.get('name'):
            domain.append(('name', 'ilike', params['name']))
        if params.get('status'):
            domain.append(('tmf_status', '=', params['status']))
        return domain

    # -----------------------
    # Individual
    # -----------------------

    @http.route(f'{TMF_BASE}/individual', type='http', auth='public', methods=['GET'], csrf=False)
    def list_individuals(self, **kwargs):
        limit = int(kwargs.get('limit') or 50)
        offset = int(kwargs.get('offset') or 0)
        fields_param = kwargs.get('fields')

        partners = request.env['res.partner'].sudo().search(
            self._partner_domain_for_individual(kwargs),
            limit=limit, offset=offset, order='id asc'
        )
        data = [self._select_fields(p.to_tmf_json(), fields_param) for p in partners]
        return self._json(data)

    @http.route(f'{TMF_BASE}/individual', type='http', auth='public', methods=['POST'], csrf=False)
    def create_individual(self, **kwargs):
        payload = self._parse_json_body()

        # Mandatory fields per TMF632 user guide: familyName, givenName, @type
        if payload.get('@type') and payload.get('@type') != 'Individual':
            return self._error(400, "Bad Request", "@type must be 'Individual' for this endpoint")

        if not payload.get('givenName') or not payload.get('familyName'):
            return self._error(400, "Bad Request", "Missing mandatory fields: givenName, familyName, @type")

        if payload.get('@type') is None:
            return self._error(400, "Bad Request", "Missing mandatory field: @type")

        vals = {
            'is_company': False,
            'tmf_managed': True,
            'tmf_given_name': payload.get('givenName'),
            'tmf_family_name': payload.get('familyName'),
            # Keep Odoo's display name meaningful
            'name': f"{payload.get('givenName')} {payload.get('familyName')}",
            'tmf_status': payload.get('status') or 'initialized',
        }

        partner = request.env['res.partner'].sudo().create(vals)
        body = partner.to_tmf_json()
        headers = [('Location', body.get('href', ''))]
        return self._json(body, status=201, headers=headers)

    @http.route(f'{TMF_BASE}/individual/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_individual(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        fields_param = kwargs.get('fields')
        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1)
        if not partner:
            # Also allow numeric id fallback
            if tmf_id.isdigit():
                partner = request.env['res.partner'].sudo().browse(int(tmf_id))
                if not partner.exists() or partner.is_company:
                    partner = False
        if not partner:
            return self._error(404, "Not Found", f"Individual {tmf_id} not found")
        return self._json(self._select_fields(partner.to_tmf_json(), fields_param))

    @http.route(f'{TMF_BASE}/individual/<string:tmf_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_individual(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        # JSON Merge Patch is mandatory; enforce content type
        ctype = (request.httprequest.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        allowed = {'application/merge-patch+json', 'application/json'}
        if ctype not in allowed:
            return self._error(415, "Unsupported Media Type", "Use Content-Type: application/merge-patch+json (or application/json)")

        payload = self._parse_json_body()

        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1)
        if not partner and tmf_id.isdigit():
            partner = request.env['res.partner'].sudo().browse(int(tmf_id))
            if not partner.exists() or partner.is_company:
                partner = False
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

        # Update display name if name parts changed
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
        type='http',
        auth='public',
        methods=['DELETE'],
        csrf=False,
    )
    def delete_individual(self, tmf_id=None, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id or kwargs.get('id') or '')
        if "/" in tmf_id:
            tmf_id = tmf_id.split("/", 1)[0].strip()
        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id), ('is_company', '=', False)], limit=1)
        if not partner and tmf_id.isdigit():
            partner = request.env['res.partner'].sudo().browse(int(tmf_id))
            if not partner.exists() or partner.is_company:
                partner = False
        if partner:
            try:
                partner.unlink()
            except Exception:
                # Keep DELETE idempotent for CTK even if record vanished concurrently.
                pass
        return request.make_response('', status=204)

    # -----------------------
    # Organization
    # -----------------------

    @http.route(f'{TMF_BASE}/organization', type='http', auth='public', methods=['GET'], csrf=False)
    def list_organizations(self, **kwargs):
        limit = int(kwargs.get('limit') or 50)
        offset = int(kwargs.get('offset') or 0)
        fields_param = kwargs.get('fields')

        partners = request.env['res.partner'].sudo().search(
            self._partner_domain_for_org(kwargs),
            limit=limit, offset=offset, order='id asc'
        )
        data = [self._select_fields(p.to_tmf_json(), fields_param) for p in partners]
        return self._json(data)

    @http.route(f'{TMF_BASE}/organization', type='http', auth='public', methods=['POST'], csrf=False)
    def create_organization(self, **kwargs):
        payload = self._parse_json_body()

        if payload.get('@type') and payload.get('@type') != 'Organization':
            return self._error(400, "Bad Request", "@type must be 'Organization' for this endpoint")

        if payload.get('@type') is None:
            return self._error(400, "Bad Request", "Missing mandatory field: @type")

        if not payload.get('name'):
            return self._error(400, "Bad Request", "Missing mandatory field: name")

        vals = {
            'is_company': True,
            'tmf_managed': True,
            'name': payload.get('name'),
            'tmf_status': payload.get('status') or 'initialized',
        }
        partner = request.env['res.partner'].sudo().create(vals)
        body = partner.to_tmf_json()
        headers = [('Location', body.get('href', ''))]
        return self._json(body, status=201, headers=headers)

    @http.route(f'{TMF_BASE}/organization/<string:tmf_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_organization(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        fields_param = kwargs.get('fields')
        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1)
        if not partner:
            if tmf_id.isdigit():
                partner = request.env['res.partner'].sudo().browse(int(tmf_id))
                if not partner.exists() or not partner.is_company:
                    partner = False
        if not partner:
            return self._error(404, "Not Found", f"Organization {tmf_id} not found")
        return self._json(self._select_fields(partner.to_tmf_json(), fields_param))

    @http.route(f'{TMF_BASE}/organization/<string:tmf_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_organization(self, tmf_id, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id)
        ctype = (request.httprequest.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        allowed = {'application/merge-patch+json', 'application/json'}
        if ctype not in allowed:
            return self._error(415, "Unsupported Media Type", "Use Content-Type: application/merge-patch+json (or application/json)")

        payload = self._parse_json_body()

        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1)
        if not partner and tmf_id.isdigit():
            partner = request.env['res.partner'].sudo().browse(int(tmf_id))
            if not partner.exists() or not partner.is_company:
                partner = False
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
        type='http',
        auth='public',
        methods=['DELETE'],
        csrf=False,
    )
    def delete_organization(self, tmf_id=None, **kwargs):
        tmf_id = self._normalize_tmf_id(tmf_id or kwargs.get('id') or '')
        if "/" in tmf_id:
            tmf_id = tmf_id.split("/", 1)[0].strip()
        partner = request.env['res.partner'].sudo().search([('tmf_id', '=', tmf_id), ('is_company', '=', True)], limit=1)
        if not partner and tmf_id.isdigit():
            partner = request.env['res.partner'].sudo().browse(int(tmf_id))
            if not partner.exists() or not partner.is_company:
                partner = False
        if partner:
            try:
                partner.unlink()
            except Exception:
                # Keep DELETE idempotent for CTK even if record vanished concurrently.
                pass
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
        # Defensive fallback for CTK URL variants that may bypass typed routes.
        # Keep DELETE idempotent for party resources expected by CTK.
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
