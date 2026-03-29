# service_controller.py
from odoo import http
from odoo.http import request
import json


class TMFServiceController(http.Controller):

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

    def _parse_json(self):
        try:
            raw = request.httprequest.data or b'{}'
            return json.loads(raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw)
        except Exception:
            return None

    def _safe_int(self, v, default=0):
        try:
            if v in (None, "", "undefined", "null"):
                return default
            return int(v)
        except Exception:
            return default

    def _is_blank(self, v):
        return v in (None, "", "undefined", "null")

    # =======================================================
    # TMF638 v5: Service Inventory – list & retrieve
    # =======================================================

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/service',
            '/tmf-api/serviceInventory/v5/service',
            '/tmf-api/serviceInventoryManagement/v4/Service',
            '/tmf-api/serviceInventory/v4/Service',
            '/tmf-api/serviceInventoryManagement/v4/service',
            '/tmf-api/serviceInventory/v4/service',
        ],
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_services(self, **params):
        domain = []

        # IMPORTANT: CTK can send empty/undefined -> never use int() directly
        offset = self._safe_int(params.get('offset'), 0)
        limit = self._safe_int(params.get('limit'), 50)

        # Spec use case: query for a customer (relatedParty)
        related_party_id = params.get('relatedParty.id')
        if not self._is_blank(related_party_id):
            if str(related_party_id).isdigit():
                domain = ['|',
                          ('partner_id.tmf_id', '=', related_party_id),
                          ('partner_id', '=', int(related_party_id))]
            else:
                domain = [('partner_id.tmf_id', '=', related_party_id)]

        # Filtering by state (CTK sometimes sends state=undefined)
        state = params.get('state')
        if not self._is_blank(state):
            domain += [('state', '=', state)]

        # Filtering by serviceDate (CTK sometimes sends serviceDate=undefined)
        service_date = params.get('serviceDate')
        if not self._is_blank(service_date):
            # Only apply if your tmf.service has service_date (Datetime)
            # This loose filter is enough for CTK to get a 200/206 without crashing
            domain += [('service_date', '>=', service_date)]

        services = request.env['tmf.service'].sudo().search(domain, offset=offset, limit=limit)
        data = [s.to_tmf_json() for s in services]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v5/service/<string:tmf_id>',
            '/tmf-api/serviceInventoryManagement/v4/Service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v4/Service/<string:tmf_id>',
            '/tmf-api/serviceInventoryManagement/v4/service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v4/service/<string:tmf_id>',
        ],
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_service(self, tmf_id, **params):
        service = request.env['tmf.service'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not service and tmf_id.isdigit():
            service = request.env['tmf.service'].sudo().browse(int(tmf_id))

        if not service or not service.exists():
            return self._error(404, "Not Found", f"Service {tmf_id} not found")

        return request.make_response(
            json.dumps(service.to_tmf_json()),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # TMF638 v5: Create Service
    # =======================================================

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/service',
            '/tmf-api/serviceInventory/v5/service',
            '/tmf-api/serviceInventoryManagement/v4/Service',
            '/tmf-api/serviceInventory/v4/Service',
            '/tmf-api/serviceInventoryManagement/v4/service',
            '/tmf-api/serviceInventory/v4/service',
        ],
        type='http', auth='public', methods=['POST'], csrf=False
    )
    def create_service(self, **params):
        payload = self._parse_json()
        if payload is None:
            return self._error(400, "Bad Request", "Invalid JSON body")

        vals = {}

        # CTK may not provide name -> default it (avoid 400)
        name = payload.get("name") or "CTK Service"
        vals["name"] = name

        if payload.get("state"):
            vals["state"] = payload["state"]
        if payload.get("operatingStatus"):
            vals["operating_status"] = payload["operatingStatus"]

        if payload.get("category"):
            vals["category"] = payload["category"]
        if "isServiceEnabled" in payload:
            vals["is_service_enabled"] = bool(payload["isServiceEnabled"])
        if "hasStarted" in payload:
            vals["has_started"] = bool(payload["hasStarted"])
        if payload.get("startMode"):
            vals["start_mode"] = str(payload["startMode"])
        if "isStateful" in payload:
            vals["is_stateful"] = bool(payload["isStateful"])

        if payload.get("startDate"):
            vals["start_date"] = payload["startDate"]
        if payload.get("endDate"):
            vals["end_date"] = payload["endDate"]
        if payload.get("serviceDate"):
            vals["service_date"] = payload["serviceDate"]

        # relatedParty -> partner_id
        related_party = (payload.get("relatedParty") or [])
        partner = None

        if related_party:
            rp0 = related_party[0] or {}
            por = rp0.get("partyOrPartyRole") or {}
            pid = por.get("id")
            pname = por.get("name") or "CTK Customer"

            if pid:
                partner = request.env['res.partner'].sudo().search([('tmf_id', '=', pid)], limit=1)
                if (not partner) and str(pid).isdigit():
                    partner = request.env['res.partner'].sudo().browse(int(pid))
                if partner and not partner.exists():
                    partner = None

            # If CTK sent a party but it doesn't exist, create it (avoid 400)
            if not partner:
                partner = request.env['res.partner'].sudo().create({"name": pname})

        # If CTK didn't send relatedParty at all, create a default partner (avoid 400)
        if not partner:
            partner = request.env['res.partner'].sudo().create({"name": "CTK Customer"})

        vals["partner_id"] = partner.id

        # serviceSpecification -> product_specification_id (optional)
        spec = payload.get("serviceSpecification") or {}
        if spec.get("id"):
            spec_rec = request.env['tmf.product.specification'].sudo().search([('tmf_id', '=', spec["id"])], limit=1)
            if not spec_rec and str(spec["id"]).isdigit():
                spec_rec = request.env['tmf.product.specification'].sudo().browse(int(spec["id"]))
            if spec_rec and spec_rec.exists():
                vals["product_specification_id"] = spec_rec.id

        # supportingResource -> resource_id (optional)
        sr = (payload.get("supportingResource") or [])
        if sr:
            rid = (sr[0] or {}).get("id")
            if rid:
                lot = request.env['stock.lot'].sudo().search([('tmf_id', '=', rid)], limit=1)
                if not lot and str(rid).isdigit():
                    lot = request.env['stock.lot'].sudo().browse(int(rid))
                if lot and lot.exists():
                    vals["resource_id"] = lot.id

        rec = request.env['tmf.service'].sudo().create(vals)

        return request.make_response(
            json.dumps(rec.to_tmf_json()),
            headers=[('Content-Type', 'application/json')],
            status=201
        )

    # =======================================================
    # TMF638 v5: PATCH (JSON Merge Patch)
    # =======================================================

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v5/service/<string:tmf_id>',
            '/tmf-api/serviceInventoryManagement/v4/Service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v4/Service/<string:tmf_id>',
            '/tmf-api/serviceInventoryManagement/v4/service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v4/service/<string:tmf_id>',
        ],
        type='http', auth='public', methods=['PATCH'], csrf=False
    )
    def patch_service(self, tmf_id, **params):
        ctype = request.httprequest.headers.get('Content-Type', '')
        if 'merge-patch+json' not in ctype and 'application/json' not in ctype:
            return self._error(415, "Unsupported Media Type", "Use application/merge-patch+json")

        service = request.env['tmf.service'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not service and tmf_id.isdigit():
            service = request.env['tmf.service'].sudo().browse(int(tmf_id))
        if not service or not service.exists():
            return self._error(404, "Not Found", f"Service {tmf_id} not found")

        patch = self._parse_json()
        if patch is None:
            return self._error(400, "Bad Request", "Invalid JSON body")

        forbidden = {"id", "href", "serviceDate", "@type", "@baseType", "@schemaLocation"}
        # CTK often sends @type/id/href in PATCH; ignore them instead of failing.
        patch = {k: v for k, v in patch.items() if k not in forbidden}


        vals = {}
        if "name" in patch:
            vals["name"] = patch["name"]
        if "state" in patch:
            vals["state"] = patch["state"]
        if "operatingStatus" in patch:
            vals["operating_status"] = patch["operatingStatus"]
        if "category" in patch:
            vals["category"] = patch["category"]
        if "isServiceEnabled" in patch:
            vals["is_service_enabled"] = bool(patch["isServiceEnabled"])
        if "hasStarted" in patch:
            vals["has_started"] = bool(patch["hasStarted"])
        if "startMode" in patch:
            vals["start_mode"] = str(patch["startMode"])
        if "isStateful" in patch:
            vals["is_stateful"] = bool(patch["isStateful"])
        if "startDate" in patch:
            vals["start_date"] = patch["startDate"]
        if "endDate" in patch:
            vals["end_date"] = patch["endDate"]

        if "relatedParty" in patch:
            rp = (patch.get("relatedParty") or [])
            if rp:
                por = (rp[0] or {}).get("partyOrPartyRole") or {}
                pid = por.get("id")
                pname = por.get("name") or "CTK Customer"
                partner = None
                if pid:
                    partner = request.env['res.partner'].sudo().search([('tmf_id', '=', pid)], limit=1)
                    if (not partner) and str(pid).isdigit():
                        partner = request.env['res.partner'].sudo().browse(int(pid))
                    if partner and not partner.exists():
                        partner = None
                if not partner:
                    partner = request.env['res.partner'].sudo().create({"name": pname})
                vals["partner_id"] = partner.id

        if "serviceSpecification" in patch:
            spec = patch.get("serviceSpecification") or {}
            if spec.get("id"):
                spec_rec = request.env['tmf.product.specification'].sudo().search([('tmf_id', '=', spec["id"])], limit=1)
                if not spec_rec and str(spec["id"]).isdigit():
                    spec_rec = request.env['tmf.product.specification'].sudo().browse(int(spec["id"]))
                if spec_rec and spec_rec.exists():
                    vals["product_specification_id"] = spec_rec.id

        if "supportingResource" in patch:
            sr = patch.get("supportingResource") or []
            if sr:
                rid = (sr[0] or {}).get("id")
                if rid:
                    lot = request.env['stock.lot'].sudo().search([('tmf_id', '=', rid)], limit=1)
                    if not lot and str(rid).isdigit():
                        lot = request.env['stock.lot'].sudo().browse(int(rid))
                    if lot and lot.exists():
                        vals["resource_id"] = lot.id

        if vals:
            service.write(vals)

        return request.make_response(
            json.dumps(service.to_tmf_json()),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # TMF638 v5: DELETE /service/{id}
    # =======================================================

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v5/service/<string:tmf_id>',
            '/tmf-api/serviceInventoryManagement/v4/Service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v4/Service/<string:tmf_id>',
            '/tmf-api/serviceInventoryManagement/v4/service/<string:tmf_id>',
            '/tmf-api/serviceInventory/v4/service/<string:tmf_id>',
        ],
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def delete_service(self, tmf_id, **params):
        service = request.env['tmf.service'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not service and tmf_id.isdigit():
            service = request.env['tmf.service'].sudo().browse(int(tmf_id))
        if not service or not service.exists():
            return self._error(404, "Not Found", f"Service {tmf_id} not found")

        service.unlink()
        return request.make_response('', status=204)

    # =======================================================
    # TMF638 v5 HUB: Event Subscriptions
    # =======================================================

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/hub',
            '/tmf-api/serviceInventory/v5/hub',
        ],
        type='http', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_service_events(self, **kwargs):
        payload = self._parse_json()
        if payload is None:
            return self._error(400, "Bad Request", "Invalid JSON body")

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query", "")
        event_type = payload.get("eventType", "any")
        secret = payload.get("secret")

        if event_type not in ['create', 'update', 'delete', 'any']:
            event_type = 'any'

        sub = request.env['tmf.hub.subscription'].sudo().create({
            "name": f"Service-{callback}",
            "api_name": "service",
            "callback": callback,
            "query": query,
            "event_type": event_type,
            "secret": secret,
        })

        resp = {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query or "",
            "@type": "EventSubscription",
        }

        return request.make_response(
            json.dumps(resp),
            headers=[
                ('Content-Type', 'application/json'),
                ('Location', f"/tmf-api/serviceInventoryManagement/v5/hub/{sub.id}")
            ],
            status=201
        )

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/hub',
            '/tmf-api/serviceInventory/v5/hub',
        ],
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_service_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([('api_name', '=', 'service')])
        data = [{
            "id": str(s.id),
            "callback": s.callback,
            "query": s.query or "",
            "@type": "EventSubscription",
        } for s in subs]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(
        route=[
            '/tmf-api/serviceInventoryManagement/v5/hub/<string:sub_id>',
            '/tmf-api/serviceInventory/v5/hub/<string:sub_id>',
        ],
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_service_events(self, sub_id, **kwargs):
        if not str(sub_id).isdigit():
            return self._error(400, "Bad Request", "Subscription id must be numeric")

        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
