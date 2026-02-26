# -*- coding: utf-8 -*-
import json
from odoo import http, fields
from odoo.http import request


class TMFServiceCatalogController(http.Controller):
    BASE = "/tmf-api/serviceCatalogManagement/v4"

    # ---------- helpers ----------
    def _json_response(self, payload, status=200, extra_headers=None):
        headers = [("Content-Type", "application/json")]
        if extra_headers:
            headers.extend(extra_headers)
        body = "" if payload is None else json.dumps(payload, ensure_ascii=False)
        return request.make_response(body, headers=headers, status=status)

    def _error(self, status=400, code="INVALID_REQUEST", reason="Bad Request", message=""):
        return self._json_response({
            "code": code,
            "reason": reason,
            "message": message,
            "status": str(status),
        }, status=status)

    def _parse_body_json(self):
        raw = request.httprequest.get_data(cache=False, as_text=True) or ""
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except Exception:
            raise ValueError("Body must be valid JSON (Content-Type: application/json)")

    def _apply_fields_filter(self, resource_json, fields_param):
        if not fields_param:
            return resource_json
        wanted = {f.strip() for f in fields_param.split(",") if f.strip()}
        keep_always = {"id", "href", "@type"}
        return {k: v for k, v in resource_json.items() if (k in wanted or k in keep_always)}

    def _find_record(self, rid):
        env = request.env["tmf.service.catalog"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if rec:
            return rec
        if rid.isdigit():
            rec = env.browse(int(rid))
            if rec.exists():
                return rec
        return env.browse([])

    # ---------- endpoints ----------
    # LIST
    @http.route([BASE, BASE + "/"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_service_catalog(self, **params):
        env = request.env["tmf.service.catalog"].sudo()
        offset = int(params.get("offset", 0) or 0)
        limit = int(params.get("limit", 100) or 100)
        fields_param = params.get("fields")

        recs = env.search([], offset=offset, limit=limit)
        out = [self._apply_fields_filter(r.to_tmf_json(), fields_param) for r in recs]
        return self._json_response(out, status=200)

    # CREATE
    @http.route([BASE, BASE + "/"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_service_catalog(self, **params):
        try:
            data = self._parse_body_json()
            if not data.get("name"):
                return self._error(400, "MISSING_ATTRIBUTE", "Missing mandatory attribute", "Field 'name' is required")

            ls = data.get("lifecycleStatus")
            if ls is False or ls is None or ls == "":
                ls = "active"
            ls = str(ls).strip().lower()
            vals = {
                "name": data.get("name"),
                "description": data.get("description"),
                "version": data.get("version"),
                "lifecycle_status": str(ls),
                "category": data.get("category") or [],
                "related_party": data.get("relatedParty") or [],
                "valid_for": data.get("validFor"),
                "last_update": fields.Datetime.now(),
            }

            rec = request.env["tmf.service.catalog"].sudo().create(vals)
            payload = rec.to_tmf_json()

            return self._json_response(
                payload,
                status=201,
                extra_headers=[("Location", payload["href"])]
            )
        except Exception as e:
            return self._error(400, "INVALID_REQUEST", "Bad Request", str(e))

    # RETRIEVE
    @http.route(BASE + "/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_service_catalog(self, rid, **params):
        fields_param = params.get("fields")
        rec = self._find_record(rid)
        if not rec:
            return self._error(404, "NOT_FOUND", "Not Found", f"ServiceCatalog '{rid}' not found")

        payload = self._apply_fields_filter(rec.to_tmf_json(), fields_param)
        return self._json_response(payload, status=200)

    # PATCH
    @http.route(BASE + "/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_service_catalog(self, rid, **params):
        try:
            rec = self._find_record(rid)
            if not rec:
                return self._error(404, "NOT_FOUND", "Not Found", f"ServiceCatalog '{rid}' not found")

            data = self._parse_body_json()
            vals = {}

            if "name" in data: vals["name"] = data.get("name")
            if "description" in data: vals["description"] = data.get("description")
            if "version" in data: vals["version"] = data.get("version")
            if "lifecycleStatus" in data: vals["lifecycle_status"] = data.get("lifecycleStatus")
            if "lastUpdate" in data: vals["last_update"] = data.get("lastUpdate")
            if "category" in data: vals["category"] = data.get("category") or []
            if "relatedParty" in data: vals["related_party"] = data.get("relatedParty") or []
            if "validFor" in data: vals["valid_for"] = data.get("validFor")

            rec.write(vals)
            return self._json_response(rec.to_tmf_json(), status=200)
        except Exception as e:
            return self._error(400, "INVALID_REQUEST", "Bad Request", str(e))

    # DELETE
    @http.route(BASE + "/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_service_catalog(self, rid, **params):
        rec = self._find_record(rid)
        if not rec:
            return self._error(404, "NOT_FOUND", "Not Found", f"ServiceCatalog '{rid}' not found")

        rec.unlink()
        # 204 No Content
        return request.make_response("", status=204)

class TMFServiceSpecificationController(http.Controller):
    BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"

    def _json_response(self, payload, status=200, extra_headers=None):
        headers = [("Content-Type", "application/json")]
        if extra_headers:
            headers.extend(extra_headers)
        body = "" if payload is None else json.dumps(payload, ensure_ascii=False)
        return request.make_response(body, headers=headers, status=status)

    def _error(self, status=400, code="INVALID_REQUEST", reason="Bad Request", message=""):
        return self._json_response({
            "code": code,
            "reason": reason,
            "message": message,
            "status": str(status),
        }, status=status)

    def _parse_body_json(self):
        raw = request.httprequest.get_data(cache=False, as_text=True) or ""
        if not raw.strip():
            return {}
        return json.loads(raw)

    def _apply_fields_filter(self, resource_json, fields_param):
        if not fields_param:
            return resource_json
        wanted = {f.strip() for f in fields_param.split(",") if f.strip()}
        keep_always = {"id", "href", "@type"}
        return {k: v for k, v in resource_json.items() if (k in wanted or k in keep_always)}

    def _find_record(self, rid):
        env = request.env["tmf.service.specification"].sudo()
        rec = env.search([("tmf_id", "=", rid)], limit=1)
        if rec:
            return rec
        if rid.isdigit():
            rec = env.browse(int(rid))
            if rec.exists():
                return rec
        return env.browse([])

    # LIST + FILTERS
    @http.route(BASE, type="http", auth="public", methods=["GET"], csrf=False)
    def list_spec(self, **params):
        env = request.env["tmf.service.specification"].sudo()
        domain = []

        # CTK filters
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        if "lifecycleStatus" in params:
            v = str(params.get("lifecycleStatus") or "").strip("'\"").strip().lower()
            if v in ("false", "0", "none", "null", ""):
                v = "active"
            domain.append(("lifecycle_status", "=ilike", v))
        if params.get("isBundle") is not None:
            # handle "true"/"false"
            v = str(params["isBundle"]).lower()
            if v in ("true", "1", "yes"):
                domain.append(("is_bundle", "=", True))
            elif v in ("false", "0", "no"):
                domain.append(("is_bundle", "=", False))

        # lastUpdate filter (CTK sometimes passes quoted value; accept raw string compare fallback)
        if params.get("lastUpdate"):
            lu = str(params["lastUpdate"]).strip("'\"")
            # try parse ISO, else do equality on stringified iso
            try:
                dt = fields.Datetime.from_string(lu)
                domain.append(("last_update", "=", dt))
            except Exception:
                pass

        offset = int(params.get("offset", 0) or 0)
        limit = int(params.get("limit", 100) or 100)
        fields_param = params.get("fields")

        recs = env.search(domain, offset=offset, limit=limit)
        out = [self._apply_fields_filter(r.to_tmf_json(), fields_param) for r in recs]
        return self._json_response(out, status=200)

    # CREATE
    @http.route(BASE, type="http", auth="public", methods=["POST"], csrf=False)
    def create_spec(self, **params):
        try:
            data = self._parse_body_json()
            if not data.get("name"):
                return self._error(400, "MISSING_ATTRIBUTE", "Missing mandatory attribute", "Field 'name' is required")

            vals = {
                "name": data.get("name"),
                "description": data.get("description"),
                "version": data.get("version"),
                "lifecycle_status": data.get("lifecycleStatus"),
                "is_bundle": bool(data.get("isBundle", False)),
                "related_party": data.get("relatedParty") or [],
                "valid_for": data.get("validFor"),
                "last_update": fields.Datetime.now(),
            }

            rec = request.env["tmf.service.specification"].sudo().create(vals)
            payload = rec.to_tmf_json()
            return self._json_response(payload, status=201, extra_headers=[("Location", payload["href"])])
        except Exception as e:
            return self._error(400, "INVALID_REQUEST", "Bad Request", str(e))

    # RETRIEVE
    @http.route(BASE + "/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_spec(self, rid, **params):
        rec = self._find_record(rid)
        if not rec:
            return self._error(404, "NOT_FOUND", "Not Found", f"ServiceSpecification '{rid}' not found")

        payload = self._apply_fields_filter(rec.to_tmf_json(), params.get("fields"))
        return self._json_response(payload, status=200)
