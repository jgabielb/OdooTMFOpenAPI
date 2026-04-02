from odoo import http
from odoo.http import request, Response
import json
import logging
from datetime import datetime

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)


class TMFCatalogController(TMFBaseController):

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_now(self):
        return datetime.utcnow().isoformat(timespec='milliseconds') + "Z"

    def _base_url(self):
        return request.httprequest.host_url.rstrip('/') + "/tmf-api/productCatalogManagement/v5"

    def _publish_event(self, resource_type, action, payload):
        event_map = {
            "productOffering": {
                "create": "ProductOfferingCreateEvent",
                "update": "ProductOfferingAttributeValueChangeEvent",
                "state_change": "ProductOfferingStateChangeEvent",
                "delete": "ProductOfferingDeleteEvent",
            },
            "productSpecification": {
                "create": "ProductSpecificationCreateEvent",
                "update": "ProductSpecificationAttributeValueChangeEvent",
                "state_change": "ProductSpecificationStateChangeEvent",
                "delete": "ProductSpecificationDeleteEvent",
            },
            "productOfferingPrice": {
                "create": "ProductOfferingPriceCreateEvent",
                "update": "ProductOfferingPriceAttributeValueChangeEvent",
                "state_change": "ProductOfferingPriceStateChangeEvent",
                "delete": "ProductOfferingPriceDeleteEvent",
            },
        }
        event_name = (event_map.get(resource_type) or {}).get(action)
        if not event_name:
            return
        try:
            request.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=resource_type,
                event_type=event_name,
                resource_json=payload,
            )
        except Exception:
            pass

    def _listener_ok(self):
        try:
            payload = self._parse_json_body()
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return self._error(400, "BAD_REQUEST", "Invalid JSON body")
        return request.make_response("", status=201)

    # -------------------------------------------------------------------------
    # Status helpers
    # -------------------------------------------------------------------------
    _SPEC_STATUS_IN = {'In Design': 'design', 'Active': 'active', 'Retired': 'retired'}
    _SPEC_STATUS_OUT = {'design': 'In Design', 'active': 'Active', 'retired': 'Retired'}
    _OFF_STATUS_IN = {'active': 'active', 'retired': 'retired', 'design': 'design',
                      'in design': 'design'}
    _OFF_STATUS_OUT = {'design': 'In Design', 'active': 'Active', 'retired': 'Retired'}

    # =======================================================
    # 1. Product Specification API
    # =======================================================

    @http.route('/tmf-api/productCatalogManagement/v5/productSpecification',
                type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def product_specification_collection(self, **params):
        if request.httprequest.method == 'POST':
            try:
                data = self._parse_json_body()
                vals = {
                    "name": data.get("name") or "ProductSpecification",
                    "version": data.get("version") or "1.0",
                    "lifecycle_status": self._SPEC_STATUS_IN.get(
                        data.get("lifecycleStatus", "In Design"), "design"
                    ),
                }
                if data.get("description"):
                    vals["description"] = data["description"]
                if data.get("brand"):
                    vals["brand"] = data["brand"]
                if data.get("productNumber"):
                    vals["product_number"] = data["productNumber"]
                if data.get("relatedParty"):
                    vals["related_party_json"] = data["relatedParty"]
                spec = request.env["tmf.product.specification"].sudo().create(vals)
                created = self._spec_to_json(spec)
                # Merge any extra inbound fields not mapped to DB
                for k, v in data.items():
                    if k not in ("id", "href", "@type", "name", "lifecycleStatus",
                                 "version", "description", "brand", "productNumber",
                                 "relatedParty"):
                        created.setdefault(k, v)
                return self._json(created, status=201)
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))

        # GET list
        domain = []
        if params.get('lifecycleStatus'):
            odoo_status = self._SPEC_STATUS_IN.get(params['lifecycleStatus'], 'design')
            domain.append(('lifecycle_status', '=', odoo_status))

        limit, offset = self._paginate_params(params)
        env = request.env['tmf.product.specification'].sudo()
        recs = env.search(domain, limit=limit, offset=offset)
        total = env.search_count(domain)
        data = [self._spec_to_json(s) for s in recs]

        if params.get('name'):
            data = [x for x in data if x.get('name') == params['name']]

        data = self._select_fields_list(data, params.get('fields'))
        return self._json(data, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(data))),
        ])

    @http.route('/tmf-api/productCatalogManagement/v5/productSpecification/<string:id>',
                type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def product_specification_individual(self, id, **params):
        spec = self._find_record('tmf.product.specification', id)
        if not spec:
            return self._error(404, "NOT_FOUND", f"ProductSpecification {id} not found")

        if request.httprequest.method == 'PATCH':
            try:
                data = self._parse_json_body()
                vals = {}
                if 'name' in data:
                    vals['name'] = data['name']
                if 'description' in data:
                    vals['description'] = data['description']
                if 'version' in data:
                    vals['version'] = data['version']
                if 'brand' in data:
                    vals['brand'] = data['brand']
                if 'productNumber' in data:
                    vals['product_number'] = data['productNumber']
                if 'lifecycleStatus' in data:
                    vals['lifecycle_status'] = self._SPEC_STATUS_IN.get(
                        data['lifecycleStatus'], 'design'
                    )
                if 'relatedParty' in data:
                    vals['related_party_json'] = data['relatedParty']
                if 'serviceSpecification' in data:
                    vals['service_specification_json'] = data['serviceSpecification']
                if 'resourceSpecification' in data:
                    vals['resource_specification_json'] = data['resourceSpecification']
                if vals:
                    spec.write(vals)
                return self._json(self._select_fields(self._spec_to_json(spec), params.get('fields')))
            except Exception as e:
                return self._error(400, "UPDATE_ERROR", str(e))

        elif request.httprequest.method == 'DELETE':
            try:
                spec.unlink()
                return Response(status=204)
            except Exception:
                return self._error(400, "DELETE_ERROR", "Could not delete")

        return self._json(self._select_fields(self._spec_to_json(spec), params.get('fields')))

    def _spec_to_json(self, s):
        payload = {
            "id": s.tmf_id or str(s.id),
            "href": f"{self._base_url()}/productSpecification/{s.tmf_id or s.id}",
            "name": s.name,
            "description": s.description or "",
            "productNumber": s.product_number or "",
            "brand": s.brand or "",
            "version": s.version,
            "lifecycleStatus": self._SPEC_STATUS_OUT.get(s.lifecycle_status, "In Design"),
            "lastUpdate": s.write_date.isoformat() + "Z" if s.write_date else None,
            "@type": "ProductSpecification",
        }
        if s.related_partner_ids:
            payload["relatedParty"] = [
                {"id": p.tmf_id or str(p.id), "name": p.name, "@type": "RelatedParty"}
                for p in s.related_partner_ids
            ]
        if s.service_specification_ids:
            payload["serviceSpecification"] = [
                {"id": ss.tmf_id, "href": ss.href, "name": ss.name,
                 "@type": "ServiceSpecificationRef"}
                for ss in s.service_specification_ids
            ]
        if s.resource_specification_ids:
            payload["resourceSpecification"] = [
                {"id": rs.tmf_id, "href": rs.href, "name": rs.name,
                 "@type": "ResourceSpecificationRef"}
                for rs in s.resource_specification_ids
            ]
        return payload

    # =======================================================
    # 2. Product Offering API
    # =======================================================

    @http.route('/tmf-api/productCatalogManagement/v5/productOffering',
                type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def product_offering_collection(self, **params):
        if request.httprequest.method == 'POST':
            try:
                data = self._parse_json_body()
                lc = (data.get("lifecycleStatus") or "Active").lower()
                vals = {
                    "name": data.get("name") or "ProductOffering",
                    "lifecycle_status": self._OFF_STATUS_IN.get(lc, "active"),
                }
                ps = data.get("productSpecification") or {}
                ps_id = str(ps.get("id") or "").strip()
                if ps_id:
                    spec = request.env["tmf.product.specification"].sudo().search(
                        [("tmf_id", "=", ps_id)], limit=1
                    )
                    if spec:
                        vals["product_specification_id"] = spec.id
                offering = request.env["product.template"].sudo().create(vals)
                if data.get("relatedParty"):
                    offering.sudo().write({"related_party_json": data["relatedParty"]})
                created = self._offering_to_json(offering)
                for k, v in data.items():
                    if k not in ("id", "href", "@type", "name", "lifecycleStatus",
                                 "productSpecification", "relatedParty"):
                        created.setdefault(k, v)
                return self._json(created, status=201)
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))

        # GET list
        domain = [('active', '=', True)]
        if params.get('name'):
            domain.append(('name', '=', params['name']))

        limit, offset = self._paginate_params(params)
        env = request.env['product.template'].sudo()
        recs = env.search(domain, limit=limit, offset=offset)
        total = env.search_count(domain)
        data = self._select_fields_list([self._offering_to_json(o) for o in recs],
                                        params.get('fields'))
        return self._json(data, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(data))),
        ])

    @http.route('/tmf-api/productCatalogManagement/v5/productOffering/<string:id>',
                type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def product_offering_individual(self, id, **params):
        offering = self._find_record('product.template', id)
        if not offering:
            return self._error(404, "NOT_FOUND", f"ProductOffering {id} not found")

        if request.httprequest.method == 'PATCH':
            try:
                data = self._parse_json_body()
                vals = {}
                if 'name' in data:
                    vals['name'] = data['name']
                if 'lifecycleStatus' in data:
                    vals['lifecycle_status'] = self._OFF_STATUS_IN.get(
                        data['lifecycleStatus'].lower(), 'active'
                    )
                if 'relatedParty' in data:
                    vals['related_party_json'] = data['relatedParty']
                if 'place' in data:
                    vals['place_json'] = data['place']
                if 'agreement' in data:
                    vals['agreement_json'] = data['agreement']
                if 'serviceSpecification' in data:
                    vals['service_specification_json'] = data['serviceSpecification']
                if 'resourceSpecification' in data:
                    vals['resource_specification_json'] = data['resourceSpecification']
                if vals:
                    offering.write(vals)
                return self._json(self._select_fields(
                    self._offering_to_json(offering), params.get('fields')
                ))
            except Exception as e:
                return self._error(400, "UPDATE_ERROR", str(e))

        elif request.httprequest.method == 'DELETE':
            try:
                offering.unlink()
                return Response(status=204)
            except Exception:
                return self._error(400, "DELETE_ERROR", "Could not delete")

        return self._json(self._select_fields(self._offering_to_json(offering), params.get('fields')))

    def _offering_to_json(self, o):
        result = {
            "id": o.tmf_id or str(o.id),
            "href": f"{self._base_url()}/productOffering/{o.tmf_id or o.id}",
            "name": o.name,
            "lifecycleStatus": self._OFF_STATUS_OUT.get(o.lifecycle_status, "Active"),
            "lastUpdate": o.write_date.isoformat() + "Z" if o.write_date else None,
            "isBundle": False,
            "@type": "ProductOffering",
            "productOfferingPrice": [],
        }
        if o.product_specification_id:
            result["productSpecification"] = {
                "id": o.product_specification_id.tmf_id or str(o.product_specification_id.id),
                "href": (o.product_specification_id.href
                         or f"{self._base_url()}/productSpecification/"
                            f"{o.product_specification_id.id}"),
                "name": o.product_specification_id.name,
                "@type": "ProductSpecificationRef",
                "@referredType": "ProductSpecification",
            }
        related_party = [
            {"id": p.tmf_id or str(p.id), "name": p.name, "@type": "RelatedParty"}
            for p in o.related_partner_ids
        ] + [
            {"id": r.tmf_id, "href": r.href, "name": r.name, "@type": "PartyRoleRef"}
            for r in o.related_party_role_ids
        ]
        if related_party:
            result["relatedParty"] = related_party
        if o.service_specification_ids:
            result["serviceSpecification"] = [
                {"id": ss.tmf_id, "href": ss.href, "name": ss.name,
                 "@type": "ServiceSpecificationRef"}
                for ss in o.service_specification_ids
            ]
        if o.resource_specification_ids:
            result["resourceSpecification"] = [
                {"id": rs.tmf_id, "href": rs.href, "name": rs.name,
                 "@type": "ResourceSpecificationRef"}
                for rs in o.resource_specification_ids
            ]
        if o.agreement_ids:
            result["agreement"] = [
                {"id": a.tmf_id, "href": a.href, "name": a.name, "@type": "AgreementRef"}
                for a in o.agreement_ids
            ]
        place = []
        if o.geographic_address_id:
            place.append({"id": o.geographic_address_id.tmf_id,
                          "href": o.geographic_address_id.href, "@type": "GeographicAddressRef"})
        if o.geographic_site_id:
            place.append({"id": o.geographic_site_id.tmf_id,
                          "href": o.geographic_site_id.href, "@type": "GeographicSiteRef"})
        if o.geographic_location_id:
            place.append({"id": o.geographic_location_id.tmf_id,
                          "href": o.geographic_location_id.href,
                          "@type": "GeographicLocationRef"})
        if place:
            result["place"] = place
        return result

    # =======================================================
    # 3. Product Offering Price API
    # =======================================================

    @http.route('/tmf-api/productCatalogManagement/v5/productOfferingPrice',
                type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def price_collection(self, **params):
        if request.httprequest.method == 'POST':
            try:
                data = self._parse_json_body()
                vals = {
                    "name": data.get("name") or "ProductOfferingPrice",
                    "version": data.get("version") or "1.0",
                    "lifecycle_status": data.get("lifecycleStatus", "active").lower(),
                }
                if data.get("description"):
                    vals["description"] = data["description"]
                if data.get("priceType"):
                    vals["price_type"] = data["priceType"]
                if data.get("price"):
                    vals["price_json"] = json.dumps(data["price"])
                # Link to offering if provided
                po_id = str((data.get("productOffering") or {}).get("id") or "").strip()
                if po_id:
                    offering = request.env["product.template"].sudo().search(
                        [("tmf_id", "=", po_id)], limit=1
                    )
                    if offering:
                        vals["offering_id"] = offering.id
                price_rec = request.env["tmf.product.offering.price"].sudo().create(vals)
                created = self._price_to_json(price_rec)
                for k, v in data.items():
                    if k not in ("id", "href", "@type", "name", "lifecycleStatus",
                                 "version", "description", "priceType", "price",
                                 "productOffering"):
                        created.setdefault(k, v)
                return self._json(created, status=201)
            except Exception as e:
                return self._error(400, "BAD_REQUEST", str(e))

        # GET list
        env = request.env['tmf.product.offering.price'].sudo()
        limit, offset = self._paginate_params(params)
        recs = env.search([], limit=limit, offset=offset)
        total = env.search_count([])
        data = self._select_fields_list([self._price_to_json(p) for p in recs],
                                        params.get('fields'))
        return self._json(data, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(data))),
        ])

    @http.route('/tmf-api/productCatalogManagement/v5/productOfferingPrice/<string:id>',
                type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def price_individual(self, id, **params):
        price = self._find_record('tmf.product.offering.price', id)
        if not price:
            return self._error(404, "NOT_FOUND", f"ProductOfferingPrice {id} not found")

        if request.httprequest.method == 'PATCH':
            try:
                data = self._parse_json_body()
                vals = {}
                if 'name' in data:
                    vals['name'] = data['name']
                if 'description' in data:
                    vals['description'] = data['description']
                if 'lifecycleStatus' in data:
                    _status_in = {'Draft': 'draft', 'Active': 'active', 'Retired': 'retired'}
                    vals['lifecycle_status'] = _status_in.get(
                        data['lifecycleStatus'], data['lifecycleStatus'].lower()
                    )
                if 'price' in data:
                    vals['price_json'] = json.dumps(data['price'])
                if vals:
                    price.write(vals)
                return self._json(self._select_fields(self._price_to_json(price), params.get('fields')))
            except Exception as e:
                return self._error(400, "UPDATE_ERROR", str(e))

        elif request.httprequest.method == 'DELETE':
            try:
                price.unlink()
                return Response(status=204)
            except Exception:
                return self._error(400, "DELETE_ERROR", "Could not delete")

        return self._json(self._select_fields(self._price_to_json(price), params.get('fields')))

    _PRICE_STATUS_OUT = {'draft': 'Draft', 'active': 'Active', 'retired': 'Retired'}

    def _price_to_json(self, p):
        result = {
            "id": p.tmf_id or str(p.id),
            "href": f"{self._base_url()}/productOfferingPrice/{p.tmf_id or p.id}",
            "name": p.name,
            "description": p.description or "",
            "version": p.version or "1.0",
            "lifecycleStatus": self._PRICE_STATUS_OUT.get(p.lifecycle_status, "Active"),
            "lastUpdate": p.write_date.isoformat() + "Z" if p.write_date else None,
            "@type": "ProductOfferingPrice",
        }
        if p.offering_id:
            result["productOffering"] = [{
                "id": p.offering_id.tmf_id or str(p.offering_id.id),
                "href": f"{self._base_url()}/productOffering/{p.offering_id.tmf_id or p.offering_id.id}",
                "name": p.offering_id.name,
                "@type": "ProductOfferingRef",
                "@referredType": "ProductOffering",
            }]
        if p.price_type:
            result["priceType"] = p.price_type
        if p.price_json:
            try:
                result["price"] = json.loads(p.price_json)
            except Exception:
                pass
        return result

    # =======================================================
    # TMF620 Hub + listeners
    # =======================================================

    @http.route('/tmf-api/productCatalogManagement/v5/hub',
                type='http', auth='public', methods=['POST'], csrf=False)
    def register_listener(self, **params):
        try:
            data = self._parse_json_body()
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
        return self._json(body, status=201)

    @http.route('/tmf-api/productCatalogManagement/v5/hub/<string:sid>',
                type='http', auth='public', methods=['DELETE'], csrf=False)
    def unregister_listener(self, sid, **params):
        rec = (request.env["tmf.hub.subscription"].sudo().browse(int(sid))
               if str(sid).isdigit() else None)
        if not rec or not rec.exists():
            return self._error(404, "NOT_FOUND", f"Hub subscription {sid} not found")
        siblings = request.env["tmf.hub.subscription"].sudo().search([
            ("callback", "=", rec.callback),
            ("api_name", "in", ["productOffering", "productSpecification",
                                "productOfferingPrice"]),
        ])
        (siblings or rec).unlink()
        return Response(status=204)

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingCreateEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_create(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingAttributeValueChangeEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_attr(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingStateChangeEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_state(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingDeleteEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_offering_delete(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationCreateEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_create(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationAttributeValueChangeEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_attr(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationStateChangeEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_state(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productSpecificationDeleteEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_product_spec_delete(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceCreateEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_create(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceAttributeValueChangeEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_attr(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceStateChangeEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_state(self, **params):
        return self._listener_ok()

    @http.route('/tmf-api/productCatalogManagement/v5/listener/productOfferingPriceDeleteEvent',
                type='http', auth='public', methods=['POST'], csrf=False)
    def listen_pop_delete(self, **params):
        return self._listener_ok()

    # =======================================================
    # Common
    # =======================================================
    def _find_record(self, model_name, id_str):
        if not id_str:
            return None
        rec = request.env[model_name].sudo().search([('tmf_id', '=', id_str)], limit=1)
        if rec:
            return rec
        if id_str.isdigit():
            rec = request.env[model_name].sudo().browse(int(id_str))
            if rec.exists():
                return rec
        return None
