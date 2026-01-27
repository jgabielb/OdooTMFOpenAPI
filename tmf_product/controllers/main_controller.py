from odoo import http
from odoo.http import request
import json
import uuid
import logging

_logger = logging.getLogger(__name__)


class TMF760ProductConfigurationController(http.Controller):

    # ---------------- Helpers ----------------

    def _json_response(self, payload, status=200, extra_headers=None):
        headers = [('Content-Type', 'application/json')]
        if extra_headers:
            headers += extra_headers
        return request.make_response(json.dumps(payload), headers=headers, status=status)

    def _error(self, status, message, code="Error"):
        return self._json_response({"code": str(status), "message": message, "@type": code}, status=status)

    def _new_id(self):
        return str(uuid.uuid4())

    def _mk_href(self, resource, rid):
        # NOTE: CTK calls base /tmf-api/productManagement/v5
        return f"/tmf-api/productManagement/v5/{resource}/{rid}"

    def _apply_fields_filter(self, obj, fields_param):
        """
        TMF 'fields' query param: return only requested top-level fields.
        Always keep id/href/@type if present (CTK-friendly).
        """
        if not fields_param or not isinstance(obj, dict):
            return obj

        keep = {f.strip() for f in fields_param.split(",") if f.strip()}
        forced = {"id", "href", "@type"}
        keep |= forced

        return {k: v for k, v in obj.items() if k in keep}

    def _list_with_pagination(self, model_name, fields_param):
        """
        Support offset/limit and return 200 or 206 with Content-Range.
        """
        Model = request.env[model_name].sudo()
        total = Model.search_count([])

        try:
            offset = int(request.params.get("offset", 0))
        except Exception:
            offset = 0
        try:
            limit = int(request.params.get("limit", 0))
        except Exception:
            limit = 0

        if limit and limit > 0:
            recs = Model.search([], offset=offset, limit=limit)
        else:
            recs = Model.search([])

        items = []
        for r in recs:
            obj = r.resource_json or r.response_payload or r.request_payload or {}
            if not isinstance(obj, dict):
                obj = {}

            # Ensure required fields for schema
            obj.setdefault("id", r.tmf_id)
            obj.setdefault("href", r.href)

            # Infer @type per collection
            if model_name == "tmf.check.product.configuration":
                obj.setdefault("@type", "CheckProductConfiguration")
                obj.setdefault("state", r.state or "acknowledged")
                obj.setdefault("checkProductConfigurationItem", obj.get("checkProductConfigurationItem") or [])
            else:
                obj.setdefault("@type", "QueryProductConfiguration")
                obj.setdefault("state", r.state or "acknowledged")
                obj.setdefault("queryProductConfigurationItem", obj.get("queryProductConfigurationItem") or [])

            items.append(self._apply_fields_filter(obj, fields_param))

        # Partial content?
        if limit and limit > 0 and (offset + len(recs)) < total:
            start = offset
            end = offset + len(recs) - 1 if len(recs) else offset
            cr = f"items {start}-{end}/{total}"
            return self._json_response(items, status=206, extra_headers=[("Content-Range", cr)])

        return self._json_response(items, status=200)

    # ---------------- CHECK PRODUCT CONFIGURATION ----------------

    @http.route([
        "/tmf-api/productManagement/v5/checkProductConfiguration",
        "/tmf-api/productManagement/v5/checkProductConfiguration/",
    ], type="http", auth="public", methods=["POST"], csrf=False)
    def post_check_product_configuration(self, **params):
        try:
            payload = json.loads(request.httprequest.data or b"{}")
            rid = self._new_id()
            href = self._mk_href("checkProductConfiguration", rid)

            # ---- Build TMF760 resource (schema-shaped) ----
            # Minimal but compliant structure:
            # - @type, id, href, state, checkProductConfigurationItem[]
            resource = dict(payload) if isinstance(payload, dict) else {}
            resource.update({
                "id": rid,
                "href": href,
                "@type": resource.get("@type") or "CheckProductConfiguration",
                "state": resource.get("state") or "acknowledged",
            })

            # Ensure mandatory list exists (CTK expects object shape)
            if "checkProductConfigurationItem" not in resource:
                resource["checkProductConfigurationItem"] = []

            # Ensure each item has @type + id if present/required
            for idx, item in enumerate(resource.get("checkProductConfigurationItem") or []):
                if isinstance(item, dict):
                    item.setdefault("@type", "CheckProductConfigurationItem")
                    item.setdefault("id", item.get("id") or f"{idx+1:02d}")

            rec = request.env["tmf.check.product.configuration"].sudo().create({
                "tmf_id": rid,
                "href": href,
                "state": resource["state"],
                "resource_json": resource,
            })

            location = request.httprequest.host_url.rstrip("/") + href
            fields_param = request.params.get("fields")
            return self._json_response(self._apply_fields_filter(resource, fields_param), status=201,
                                      extra_headers=[("Location", location)])

        except Exception as e:
            _logger.exception("POST /checkProductConfiguration failed")
            return self._error(400, f"Create failed: {e}")

    @http.route([
        "/tmf-api/productManagement/v5/checkProductConfiguration",
        "/tmf-api/productManagement/v5/checkProductConfiguration/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_check_product_configuration(self, **params):
        fields_param = request.params.get("fields")
        return self._list_with_pagination("tmf.check.product.configuration", fields_param)

    @http.route([
        "/tmf-api/productManagement/v5/checkProductConfiguration/<string:rid>",
        "/tmf-api/productManagement/v5/checkProductConfiguration/<string:rid>/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_check_product_configuration_by_id(self, rid, **params):
        rec = request.env["tmf.check.product.configuration"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return self._error(404, f"CheckProductConfiguration {rid} not found")

        fields_param = request.params.get("fields")
        obj = rec.resource_json or {}
        return self._json_response(self._apply_fields_filter(obj, fields_param), status=200)

    # ---------------- QUERY PRODUCT CONFIGURATION ----------------

    @http.route([
        "/tmf-api/productManagement/v5/queryProductConfiguration",
        "/tmf-api/productManagement/v5/queryProductConfiguration/",
    ], type="http", auth="public", methods=["POST"], csrf=False)
    def post_query_product_configuration(self, **params):
        try:
            payload = json.loads(request.httprequest.data or b"{}")
            rid = self._new_id()
            href = self._mk_href("queryProductConfiguration", rid)

            resource = dict(payload) if isinstance(payload, dict) else {}
            resource.update({
                "id": rid,
                "href": href,
                "@type": resource.get("@type") or "QueryProductConfiguration",
                "state": resource.get("state") or "acknowledged",
            })

            if "queryProductConfigurationItem" not in resource:
                resource["queryProductConfigurationItem"] = []

            for idx, item in enumerate(resource.get("queryProductConfigurationItem") or []):
                if isinstance(item, dict):
                    item.setdefault("@type", "QueryProductConfigurationItem")
                    item.setdefault("id", item.get("id") or f"{idx+1:02d}")

            rec = request.env["tmf.query.product.configuration"].sudo().create({
                "tmf_id": rid,
                "href": href,
                "state": resource["state"],
                "resource_json": resource,
            })

            location = request.httprequest.host_url.rstrip("/") + href
            fields_param = request.params.get("fields")
            return self._json_response(self._apply_fields_filter(resource, fields_param), status=201,
                                      extra_headers=[("Location", location)])

        except Exception as e:
            _logger.exception("POST /queryProductConfiguration failed")
            return self._error(400, f"Create failed: {e}")

    @http.route([
        "/tmf-api/productManagement/v5/queryProductConfiguration",
        "/tmf-api/productManagement/v5/queryProductConfiguration/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_query_product_configuration(self, **params):
        fields_param = request.params.get("fields")
        return self._list_with_pagination("tmf.query.product.configuration", fields_param)

    @http.route([
        "/tmf-api/productManagement/v5/queryProductConfiguration/<string:rid>",
        "/tmf-api/productManagement/v5/queryProductConfiguration/<string:rid>/",
    ], type="http", auth="public", methods=["GET"], csrf=False)
    def get_query_product_configuration_by_id(self, rid, **params):
        rec = request.env["tmf.query.product.configuration"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return self._error(404, f"QueryProductConfiguration {rid} not found")

        fields_param = request.params.get("fields")
        obj = rec.resource_json or {}
        return self._json_response(self._apply_fields_filter(obj, fields_param), status=200)
