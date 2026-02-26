# resource_controller.py (REPLACE ENTIRE FILE)

from odoo import http
from odoo.http import request
import json
import uuid


API_BASE = "/tmf-api/resourceInventoryManagement/v4"


class TMFResourceController(http.Controller):

    # ---------------------------
    # helpers
    # ---------------------------
    def _json_response(self, body, status=200, headers=None):
        headers = headers or []
        base_headers = [('Content-Type', 'application/json')]
        return request.make_response(
            json.dumps(body) if body is not None else '',
            headers=base_headers + headers,
            status=status
        )

    def _error(self, status, reason, message):
        return self._json_response({
            "code": str(status),
            "reason": reason,
            "message": message,
        }, status=status)

    def _apply_fields(self, data, fields_param):
        """
        TMF639: Attribute selection enabled for all first-level attributes via ?fields=... :contentReference[oaicite:6]{index=6}
        """
        if not fields_param:
            return data
        wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
        if not wanted:
            return data

        # only first-level keys. support @type, @baseType, etc as normal keys.
        wanted_set = set(wanted) | {"id", "href", "@type"}
        return {k: data.get(k) for k in wanted_set if k in data}

    def _safe_tmf_json(self, rec):
        try:
            return rec.to_tmf_json()
        except Exception:
            rid = getattr(rec, "tmf_id", None) or str(rec.id)
            return {
                "id": rid,
                "href": f"/tmf-api/resourceInventoryManagement/v4/resource/{rid}",
                "@type": "Resource",
                "name": rec.name or rec.display_name,
                "resourceStatus": getattr(rec, "resource_status", None) or "installed",
            }

    def _parse_json_body(self):
        try:
            raw = request.httprequest.data or b'{}'
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def _find_resource(self, tmf_id):
        # tmf_id in your model mixin is stored as string; fallback to numeric id.
        res = request.env['stock.lot'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if res:
            return res
        if str(tmf_id).isdigit():
            return request.env['stock.lot'].sudo().browse(int(tmf_id))
        return request.env['stock.lot'].sudo().browse([])
    
    def _get_default_product(self):
        Product = request.env['product.product'].sudo()

        # 1) Prefer a previously configured default_code if it exists
        p = Product.search([('default_code', '=', 'TMF639_DEFAULT_RESOURCE')], limit=1)
        if p:
            return p

        # 2) Otherwise just take ANY existing storable/stockable-like product
        #    (we avoid setting product.template.type because your instance rejects 'product')
        p = Product.search([], limit=1)
        if p:
            return p

        raise ValueError("No product.product found. Create at least one product in Odoo.")


    def _find_product_from_payload(self, payload):
        # If client sends resourceSpecification.id, try to map it to product by tmf_id or numeric id
        spec = payload.get("resourceSpecification") or {}
        spec_id = spec.get("id")
        if not spec_id:
            return None
        Product = request.env['product.product'].sudo()
        p = Product.search([('tmf_id', '=', str(spec_id))], limit=1)
        if p:
            return p
        if str(spec_id).isdigit():
            p = Product.browse(int(spec_id))
            if p.exists():
                return p
        return None


    # =======================================================
    # RESOURCE INVENTORY – CRUD
    # =======================================================

    @http.route(
        f'{API_BASE}/resource',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_resources(self, **params):
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 20))
        fields_param = params.get('fields')

        domain = []

        name = params.get('name')
        if name:
            domain.append(('name', '=', name))

        serial_number = params.get('serialNumber')
        if serial_number:
            domain.append(('name', '=', serial_number))

        resource_status = params.get('resourceStatus')
        if resource_status:
            domain.append(('resource_status', '=', resource_status))

        # NOTE: keeping your custom filter (not in spec, but harmless)
        product_id_param = params.get('product.id')
        if product_id_param:
            domain += ['|',
                       ('product_id.tmf_id', '=', product_id_param),
                       ('product_id', '=', int(product_id_param)) if product_id_param.isdigit() else ('id', '=', 0)]

        resources = request.env['stock.lot'].sudo().search(domain, offset=offset, limit=limit, order='id desc')
        payload = [self._apply_fields(self._safe_tmf_json(r), fields_param) for r in resources]
        return self._json_response(payload, status=200)

    @http.route(
        f'{API_BASE}/resource/<string:tmf_id>',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def get_resource(self, tmf_id, **params):
        fields_param = params.get('fields')
        res = self._find_resource(tmf_id)
        if not res or not res.exists():
            return self._error(404, "Not Found", f"Resource {tmf_id} not found")

        payload = self._apply_fields(self._safe_tmf_json(res), fields_param)
        return self._json_response(payload, status=200)

    @http.route(f'{API_BASE}/resource', type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        payload = self._parse_json_body()
        if payload is None:
            return self._error(400, "Bad Request", "Invalid JSON body")

        name = payload.get("name") or payload.get("serialNumber") or payload.get("value")
        if not name:
            return self._error(400, "Bad Request", "name is required")

        tmf_id = payload.get("id") or str(uuid.uuid4())

        # product_id is mandatory for stock.lot -> must be set
        try:
            prod = self._find_product_from_payload(payload) or self._get_default_product()
        except Exception as e:
            return self._error(422, "Unprocessable Entity", str(e))

        vals = {
            "name": name,
            "product_id": prod.id,
            "tmf_id": tmf_id,  # from your tmf.model.mixin
        }

        if payload.get("resourceStatus"):
            vals["resource_status"] = payload["resourceStatus"]

        # Avoid duplicate stock.lot uniqueness crashes on repeated CTK runs:
        # if the same serial/name already exists for the chosen product, reuse it.
        existing = request.env['stock.lot'].sudo().search(
            [('name', '=', name), ('product_id', '=', prod.id)],
            limit=1,
            order='id desc',
        )
        if existing:
            if payload.get("resourceStatus") and hasattr(existing, "resource_status"):
                existing.write({"resource_status": payload["resourceStatus"]})
            body = self._safe_tmf_json(existing)
            location = f"{API_BASE}/resource/{body.get('id')}"
            return self._json_response(body, status=201, headers=[('Location', location)])

        try:
            rec = request.env['stock.lot'].sudo().create(vals)
        except Exception as e:
            # IMPORTANT: return JSON, not HTML
            return self._error(422, "Unprocessable Entity", str(e))

        body = self._safe_tmf_json(rec)
        location = f"{API_BASE}/resource/{body.get('id')}"
        return self._json_response(body, status=201, headers=[('Location', location)])

    @http.route(
        f'{API_BASE}/resource/<string:tmf_id>',
        type='http', auth='public', methods=['PATCH'], csrf=False
    )
    def patch_resource(self, tmf_id, **params):
        """
        TMF639: PATCH supports JSON Merge Patch (RFC7386) and id/href are non-patchable :contentReference[oaicite:9]{index=9}
        """
        content_type = (request.httprequest.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type not in ("merge-patch/json", "application/merge-patch+json", "application/json"):
            return self._error(415, "Unsupported Media Type", "Use Content-Type: merge-patch/json")

        payload = self._parse_json_body()
        if payload is None:
            return self._error(400, "Bad Request", "Invalid JSON body")

        if "id" in payload or "href" in payload:
            return self._error(400, "Bad Request", "id and href are not patchable")

        res = self._find_resource(tmf_id)
        if not res or not res.exists():
            return self._error(404, "Not Found", f"Resource {tmf_id} not found")

        vals = {}
        if "name" in payload:
            vals["name"] = payload["name"]
        if "resourceStatus" in payload:
            vals["resource_status"] = payload["resourceStatus"]

        if vals:
            res.sudo().write(vals)

        return self._json_response(self._safe_tmf_json(res), status=200)

    @http.route(
        f'{API_BASE}/resource/<string:tmf_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def delete_resource(self, tmf_id, **params):
        """
        TMF639: DELETE /resource/{id} returns 204 :contentReference[oaicite:10]{index=10}
        """
        res = self._find_resource(tmf_id)
        if not res or not res.exists():
            return self._error(404, "Not Found", f"Resource {tmf_id} not found")

        res.sudo().unlink()
        return request.make_response('', status=204)

    # =======================================================
    # HUB – EVENT SUBSCRIPTIONS
    # =======================================================

    @http.route(
        f'{API_BASE}/hub',
        type='http', auth='public', methods=['POST'], csrf=False
    )
    def subscribe_resource_inventory_events(self, **kwargs):
        """
        TMF hub register listener pattern: POST /hub {"callback":"..."} returns 201 + Location :contentReference[oaicite:11]{index=11}
        """
        payload = self._parse_json_body()
        if payload is None:
            return self._error(400, "Bad Request", "Invalid JSON body")

        callback = payload.get("callback")
        if not callback:
            return self._error(400, "Bad Request", "callback is required")

        query = payload.get("query")
        event_type = payload.get("eventType", "any")
        secret = payload.get("secret")

        if event_type not in ['create', 'update', 'delete', 'any']:
            event_type = 'any'

        sub = request.env['tmf.hub.subscription'].sudo().create({
            "name": f"ResourceInventory-{callback}",
            "api_name": "resourceInventory",
            "callback": callback,
            "query": query,
            "event_type": event_type,
            "secret": secret,
        })

        body = {
            "id": str(sub.id),
            "callback": sub.callback,
            "query": sub.query,
            "eventType": sub.event_type,
            "@type": "EventSubscription",
        }
        location = f"{API_BASE}/hub/{sub.id}"
        return self._json_response(body, status=201, headers=[('Location', location)])

    @http.route(
        f'{API_BASE}/hub',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def list_resource_inventory_subscriptions(self, **params):
        subs = request.env['tmf.hub.subscription'].sudo().search([('api_name', '=', 'resourceInventory')])
        data = [{
            "id": str(s.id),
            "callback": s.callback,
            "query": s.query,
            "eventType": s.event_type,
            "@type": "EventSubscription",
        } for s in subs]
        return self._json_response(data, status=200)

    @http.route(
        f'{API_BASE}/hub/<string:sub_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    def unsubscribe_resource_inventory_events(self, sub_id, **kwargs):
        subs = request.env['tmf.hub.subscription'].sudo().browse(int(sub_id))
        if not subs.exists():
            return self._error(404, "Not Found", f"Subscription {sub_id} not found")

        subs.unlink()
        return request.make_response('', status=204)
