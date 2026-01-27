from odoo import http
from odoo.http import request
import json

CATALOG_PATH = "/tmf-api/resourceCatalogManagement/v5/resourceCatalog"
SPEC_PATH    = "/tmf-api/resourceCatalogManagement/v5/resourceSpecification"


class TMFResourceCatalogController(http.Controller):
    @http.route(CATALOG_PATH, type='http', auth='public', methods=['GET'], csrf=False)
    def list_catalogs(self, **params):
        records = request.env['tmf.resource.catalog'].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json(fields=params.get("fields")) for r in records]),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(CATALOG_PATH, type='http', auth='public', methods=['POST'], csrf=False)
    def create_catalog(self, **params):
        data = json.loads(request.httprequest.data or b"{}")
        rec = request.env['tmf.resource.catalog'].sudo().create_from_tmf(data)
        return request.make_response(json.dumps(rec.to_tmf_json()), status=201)

    @http.route(f"{CATALOG_PATH}/<string:rid>", type='http', auth='public', methods=['GET'], csrf=False)
    def get_catalog(self, rid, **params):
        rec = request.env['tmf.resource.catalog'].sudo().search([('tmf_id', '=', rid)], limit=1)
        if not rec:
            return request.make_response(json.dumps({"code":"404","reason":"Not Found","message":"ResourceCatalog not found","status":"404"}), status=404)
        return request.make_response(json.dumps(rec.to_tmf_json(fields=params.get("fields"))), headers=[('Content-Type', 'application/json')])

    @http.route(f"{CATALOG_PATH}/<string:rid>", type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_catalog(self, rid, **params):
        rec = request.env['tmf.resource.catalog'].sudo().search([('tmf_id', '=', rid)], limit=1)
        if not rec:
            return request.make_response(json.dumps({"code":"404","reason":"Not Found","message":"ResourceCatalog not found","status":"404"}), status=404)
        rec.unlink()
        return request.make_response("", status=204)


class TMFResourceSpecificationController(http.Controller):
    @http.route(SPEC_PATH, type='http', auth='public', methods=['GET'], csrf=False)
    def list_rs(self, **params):
        domain = []
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        records = request.env["tmf.resource.specification"].sudo().search(domain)
        payload = [r.to_tmf_json(fields=params.get("fields")) for r in records]
        return request.make_response(json.dumps(payload), headers=[('Content-Type', 'application/json')])

    @http.route(SPEC_PATH, type='http', auth='public', methods=['POST'], csrf=False)
    def create_rs(self, **params):
        data = json.loads(request.httprequest.data or b"{}")
        rec = request.env["tmf.resource.specification"].sudo().create_from_tmf(data)
        return request.make_response(json.dumps(rec.to_tmf_json()), status=201, headers=[('Content-Type', 'application/json')])

    @http.route(f"{SPEC_PATH}/<string:rid>", type='http', auth='public', methods=['GET'], csrf=False)
    def get_rs(self, rid, **params):
        rec = request.env["tmf.resource.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return request.make_response(json.dumps({"code":"404","reason":"Not Found","message":"ResourceSpecification not found","status":"404"}), status=404)
        return request.make_response(json.dumps(rec.to_tmf_json(fields=params.get("fields"))), headers=[('Content-Type', 'application/json')])

    @http.route(f"{SPEC_PATH}/<string:rid>", type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_rs(self, rid, **params):
        rec = request.env["tmf.resource.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return request.make_response(json.dumps({"code":"404","reason":"Not Found","message":"ResourceSpecification not found","status":"404"}), status=404)
        data = json.loads(request.httprequest.data or b"{}")
        rec.apply_tmf_patch(data)
        return request.make_response(json.dumps(rec.to_tmf_json()), headers=[('Content-Type', 'application/json')])

    @http.route(f"{SPEC_PATH}/<string:rid>", type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_rs(self, rid, **params):
        rec = request.env["tmf.resource.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return request.make_response(json.dumps({"code":"404","reason":"Not Found","message":"ResourceSpecification not found","status":"404"}), status=404)
        rec.unlink()
        return request.make_response("", status=204)
