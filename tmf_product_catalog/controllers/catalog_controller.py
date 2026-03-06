from odoo import http
from odoo.http import request, Response
import json
import logging
import uuid
from datetime import datetime

_logger = logging.getLogger(__name__)

# In-memory storage for conformance test artifacts
_MOCK_STORAGE = {
    'productSpecification': {},
    'productOffering': {},
    'productOfferingPrice': {}
}

class TMFCatalogController(http.Controller):

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    def _response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    def _error(self, status, code, message):
        return request.make_response(
            json.dumps({"code": str(code), "message": message, "reason": message}),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    def _filter_fields(self, data, fields_param):
        """Helper to filter dictionary keys based on ?fields=..."""
        if not fields_param:
            return data
        
        requested = fields_param.split(',')
        # Mandatory fields for TMF compliance/linking
        mandatory = ['id', 'href', '@type', '@referredType']
        
        def filter_dict(d):
            return {k: v for k, v in d.items() if k in requested or k in mandatory}

        if isinstance(data, list):
            return [filter_dict(item) for item in data]
        return filter_dict(data)

    def _generate_id(self):
        return str(uuid.uuid4())

    def _get_now(self):
        return datetime.utcnow().isoformat(timespec='milliseconds') + "Z"

    def _base_url(self):
        return request.httprequest.host_url.rstrip('/') + "/tmf-api/productCatalogManagement/v5"

    def _event_descriptor(self, resource_type, action):
        mapping = {
            "productOffering": {
                "api_name": "productOffering",
                "create": "ProductOfferingCreateEvent",
                "update": "ProductOfferingAttributeValueChangeEvent",
                "state_change": "ProductOfferingStateChangeEvent",
                "delete": "ProductOfferingDeleteEvent",
            },
            "productSpecification": {
                "api_name": "productSpecification",
                "create": "ProductSpecificationCreateEvent",
                "update": "ProductSpecificationAttributeValueChangeEvent",
                "state_change": "ProductSpecificationStateChangeEvent",
                "delete": "ProductSpecificationDeleteEvent",
            },
            "productOfferingPrice": {
                "api_name": "productOfferingPrice",
                "create": "ProductOfferingPriceCreateEvent",
                "update": "ProductOfferingPriceAttributeValueChangeEvent",
                "state_change": "ProductOfferingPriceStateChangeEvent",
                "delete": "ProductOfferingPriceDeleteEvent",
            },
        }
        info = mapping.get(resource_type) or {}
        event_name = info.get(action)
        if not event_name:
            return None, None
        return info.get("api_name"), event_name

    def _publish_event(self, resource_type, action, payload):
        api_name, event_name = self._event_descriptor(resource_type, action)
        if not api_name or not event_name:
            return
        try:
            request.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=api_name,
                event_type=event_name,
                resource_json=payload,
            )
        except Exception:
            pass

    def _listener_ok(self):
        try:
            payload = json.loads(request.httprequest.data or b"{}")
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return self._error(400, "BAD_REQUEST", "Invalid JSON body")
        return request.make_response("", status=201)

    # -------------------------------------------------------------------------
    # Generic Mock Storage Handlers
    # -------------------------------------------------------------------------
    def _mock_create(self, resource_type, data, id_prefix=None):
        new_id = self._generate_id()
        if id_prefix:
            new_id = f"{id_prefix}{new_id}"
        
        data['id'] = new_id
        data['href'] = f"{self._base_url()}/{resource_type}/{new_id}"
        data['lastUpdate'] = self._get_now()
        
        # Ensure @type is present
        if '@type' not in data:
            data['@type'] = resource_type[0].upper() + resource_type[1:]

        _MOCK_STORAGE[resource_type][new_id] = data
        self._publish_event(resource_type, "create", data)
        return data

    def _mock_get(self, resource_type, res_id):
        return _MOCK_STORAGE[resource_type].get(res_id)

    def _mock_patch(self, resource_type, res_id, patch_data):
        if res_id in _MOCK_STORAGE[resource_type]:
            resource = _MOCK_STORAGE[resource_type][res_id]
            previous_state = resource.get("lifecycleStatus")
            resource.update(patch_data)
            resource['lastUpdate'] = self._get_now()
            self._publish_event(resource_type, "update", resource)
            if "lifecycleStatus" in patch_data and previous_state != resource.get("lifecycleStatus"):
                self._publish_event(resource_type, "state_change", resource)
            return resource
        return None

    def _mock_delete(self, resource_type, res_id):
        if res_id in _MOCK_STORAGE[resource_type]:
            resource = _MOCK_STORAGE[resource_type][res_id]
            del _MOCK_STORAGE[resource_type][res_id]
            self._publish_event(resource_type, "delete", resource)
            return True
        return False

    # =======================================================
    # 1. Product Specification API
    # =======================================================
    
    @http.route('/tmf-api/productCatalogManagement/v5/productSpecification', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def product_specification_collection(self, **params):
        if request.httprequest.method == 'POST':
            try:
                data = json.loads(request.httprequest.data)
                if 'version' not in data: data['version'] = "1.0"
                if 'lifecycleStatus' not in data: data['lifecycleStatus'] = "In Design"
                
                created = self._mock_create('productSpecification', data)
                return self._response(created, status=201)
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))
        
        # GET List: Combine Mock + Odoo Records
        mock_data = list(_MOCK_STORAGE['productSpecification'].values())
        
        domain = []
        if params.get('lifecycleStatus'):
            status_map = {'In Design': 'design', 'Active': 'active', 'Retired': 'retired'}
            odoo_status = status_map.get(params.get('lifecycleStatus'), 'design')
            domain.append(('lifecycle_status', '=', odoo_status))
        
        odoo_specs = request.env['tmf.product.specification'].sudo().search(domain, limit=50)
        odoo_data = [self._spec_to_json(s) for s in odoo_specs]
        
        full_list = mock_data + odoo_data
        
        if params.get('name'):
            full_list = [x for x in full_list if x.get('name') == params.get('name')]
            
        return self._response(self._filter_fields(full_list, params.get('fields')))

    @http.route('/tmf-api/productCatalogManagement/v5/productSpecification/<string:id>', type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def product_specification_individual(self, id, **params):
        # 1. Try Mock
        if request.httprequest.method == 'PATCH':
            try:
                data = json.loads(request.httprequest.data)
                updated = self._mock_patch('productSpecification', id, data)
                if updated:
                    return self._response(self._filter_fields(updated, params.get('fields')))
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))
        
        elif request.httprequest.method == 'DELETE':
            if self._mock_delete('productSpecification', id):
                return Response(status=204)

        elif request.httprequest.method == 'GET':
            mock_res = self._mock_get('productSpecification', id)
            if mock_res:
                return self._response(self._filter_fields(mock_res, params.get('fields')))

        # 2. Try Odoo
        spec = self._find_record('tmf.product.specification', id)
        if not spec:
            return self._error(404, "NOT_FOUND", f"ProductSpecification {id} not found")

        if request.httprequest.method == 'PATCH':
            try:
                data = json.loads(request.httprequest.data)
                vals = {}
                if 'name' in data: vals['name'] = data['name']
                if 'description' in data: vals['description'] = data['description']
                if 'lifecycleStatus' in data:
                    status_map = {'In Design': 'design', 'Active': 'active', 'Retired': 'retired'}
                    vals['lifecycle_status'] = status_map.get(data['lifecycleStatus'], 'design')
                if vals:
                    spec.write(vals)
                return self._response(self._spec_to_json(spec))
            except Exception as e:
                return self._error(400, "UPDATE_ERROR", str(e))

        elif request.httprequest.method == 'DELETE':
            try:
                spec.unlink()
                return Response(status=204)
            except:
                return self._error(400, "DELETE_ERROR", "Could not delete")

        return self._response(self._filter_fields(self._spec_to_json(spec), params.get('fields')))

    def _spec_to_json(self, s):
        status_map_rev = {'design': 'In Design', 'active': 'Active', 'retired': 'Retired'}
        return {
            "id": s.tmf_id or str(s.id),
            "href": f"{self._base_url()}/productSpecification/{s.tmf_id or s.id}",
            "name": s.name,
            "description": s.description or "",
            "productNumber": s.product_number or "",
            "brand": s.brand or "",
            "version": s.version,
            "lifecycleStatus": status_map_rev.get(s.lifecycle_status, "In Design"),
            "lastUpdate": s.write_date.isoformat() + "Z" if s.write_date else None,
            "@type": "ProductSpecification"
        }

    # =======================================================
    # 2. Product Offering API
    # =======================================================

    @http.route('/tmf-api/productCatalogManagement/v5/productOffering', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def product_offering_collection(self, **params):
        if request.httprequest.method == 'POST':
            try:
                data = json.loads(request.httprequest.data)
                if 'lifecycleStatus' not in data: data['lifecycleStatus'] = "Active"
                created = self._mock_create('productOffering', data)
                return self._response(created, status=201)
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))

        # List
        mock_data = list(_MOCK_STORAGE['productOffering'].values())
        
        domain = [('active', '=', True)]
        if params.get('name'):
            domain.append(('name', '=', params.get('name')))
        
        odoo_recs = request.env['product.template'].sudo().search(domain, limit=50)
        odoo_data = [self._offering_to_json(o) for o in odoo_recs]
        
        full_list = mock_data + odoo_data
        return self._response(self._filter_fields(full_list, params.get('fields')))

    @http.route('/tmf-api/productCatalogManagement/v5/productOffering/<string:id>', type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def product_offering_individual(self, id, **params):
        # Mock Handling
        if request.httprequest.method == 'PATCH':
            try:
                data = json.loads(request.httprequest.data)
                updated = self._mock_patch('productOffering', id, data)
                if updated: return self._response(self._filter_fields(updated, params.get('fields')))
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))
        elif request.httprequest.method == 'DELETE':
            if self._mock_delete('productOffering', id): return Response(status=204)
        elif request.httprequest.method == 'GET':
            res = self._mock_get('productOffering', id)
            if res: return self._response(self._filter_fields(res, params.get('fields')))

        # Odoo Handling
        offering = self._find_record('product.template', id)
        if not offering:
            return self._error(404, "NOT_FOUND", f"ProductOffering {id} not found")

        if request.httprequest.method == 'PATCH':
            try:
                data = json.loads(request.httprequest.data)
                vals = {}
                if 'name' in data: vals['name'] = data['name']
                offering.write(vals)
                return self._response(self._offering_to_json(offering))
            except Exception as e:
                return self._error(400, "UPDATE_ERROR", str(e))
        elif request.httprequest.method == 'DELETE':
            offering.unlink()
            return Response(status=204)

        return self._response(self._filter_fields(self._offering_to_json(offering), params.get('fields')))

    def _offering_to_json(self, o):
        status_map_rev = {'design': 'In Design', 'active': 'Active', 'retired': 'Retired'}
        
        offering_json = {
            "id": o.tmf_id or str(o.id),
            "href": f"{self._base_url()}/productOffering/{o.tmf_id or o.id}",
            "name": o.name,
            "lifecycleStatus": status_map_rev.get(o.lifecycle_status, "Active"),
            "lastUpdate": o.write_date.isoformat() + "Z" if o.write_date else None,
            "isBundle": False,
            "@type": "ProductOffering",
            "productOfferingPrice": [], 
        }

        # FIX: Only include productSpecification if it exists. 
        # Sending None/null causes validation error "must be object".
        if o.product_specification_id:
            offering_json["productSpecification"] = {
                "id": o.product_specification_id.tmf_id or str(o.product_specification_id.id),
                "href": o.product_specification_id.href or f"{self._base_url()}/productSpecification/{o.product_specification_id.id}",
                "name": o.product_specification_id.name,
                "@type": "ProductSpecificationRef",
                "@referredType": "ProductSpecification"
            }

        return offering_json

    # =======================================================
    # 3. Product Offering Price API
    # =======================================================
    
    @http.route('/tmf-api/productCatalogManagement/v5/productOfferingPrice', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def price_collection(self, **params):
        if request.httprequest.method == 'POST':
            try:
                data = json.loads(request.httprequest.data)
                created = self._mock_create('productOfferingPrice', data)
                return self._response(created, status=201)
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))

        mock_data = list(_MOCK_STORAGE['productOfferingPrice'].values())
        return self._response(self._filter_fields(mock_data, params.get('fields')))

    @http.route('/tmf-api/productCatalogManagement/v5/productOfferingPrice/<string:id>', type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def price_individual(self, id, **params):
        if request.httprequest.method == 'PATCH':
            try:
                data = json.loads(request.httprequest.data)
                updated = self._mock_patch('productOfferingPrice', id, data)
                if updated: return self._response(self._filter_fields(updated, params.get('fields')))
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))
        elif request.httprequest.method == 'DELETE':
            if self._mock_delete('productOfferingPrice', id): return Response(status=204)
        elif request.httprequest.method == 'GET':
            res = self._mock_get('productOfferingPrice', id)
            if res: return self._response(self._filter_fields(res, params.get('fields')))

        return self._error(404, "NOT_FOUND", "Price not found")

    # =======================================================
    # TMF620 Hub + listeners
    # =======================================================
    @http.route('/tmf-api/productCatalogManagement/v5/hub', type='http', auth='public', methods=['POST'], csrf=False)
    def register_listener(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")
        except Exception:
            return self._error(400, "BAD_REQUEST", "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return self._error(400, "BAD_REQUEST", "Missing mandatory attribute: callback")
        subs = request.env["tmf.hub.subscription"].sudo().create([
            {
                "name": f"tmf620-product-offering-{callback}",
                "api_name": "productOffering",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            },
            {
                "name": f"tmf620-product-specification-{callback}",
                "api_name": "productSpecification",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            },
            {
                "name": f"tmf620-product-offering-price-{callback}",
                "api_name": "productOfferingPrice",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            },
        ])
        sub = subs[:1]
        body = {"id": str(sub.id), "callback": sub.callback, "query": sub.query or ""}
        return self._response(body, status=201)

    @http.route('/tmf-api/productCatalogManagement/v5/hub/<string:sid>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def unregister_listener(self, sid, **params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists():
            return self._error(404, "NOT_FOUND", f"Hub subscription {sid} not found")
        siblings = request.env["tmf.hub.subscription"].sudo().search([
            ("callback", "=", rec.callback),
            ("api_name", "in", ["productOffering", "productSpecification", "productOfferingPrice"]),
        ])
        (siblings or rec).unlink()
        return Response(status=204)

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingCreateEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_create(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingAttributeValueChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_attr(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingStateChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_state(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingDeleteEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_delete(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationCreateEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_create(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationAttributeValueChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_attr(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationStateChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_state(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationDeleteEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_delete(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceCreateEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_create(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceAttributeValueChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_attr(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceStateChangeEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_state(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceDeleteEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_delete(self, **params):
        return self._listener_ok()

    # =======================================================
    # Common
    # =======================================================
    def _find_record(self, model_name, id_str):
        if not id_str: return None
        rec = request.env[model_name].sudo().search([('tmf_id', '=', id_str)], limit=1)
        if rec: return rec
        if id_str.isdigit():
            rec = request.env[model_name].sudo().browse(int(id_str))
            if rec.exists(): return rec
        return None
