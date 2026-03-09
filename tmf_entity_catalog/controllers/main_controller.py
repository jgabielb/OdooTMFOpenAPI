# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
from datetime import datetime, timezone, timedelta
from dateutil import parser

API_BASE = "/tmf-api/entityCatalogManagement/v4"
RESOURCE = "entityCatalog"
BASE_PATH = f"{API_BASE}/{RESOURCE}"
RESOURCE_ES = "entitySpecification"
BASE_ES = f"{API_BASE}/{RESOURCE_ES}"

# PATCH rules from TMF662 :contentReference[oaicite:8]{index=8}
ES_PATCHABLE = {
    "attachment", "constraint", "description", "entitySpecRelationship", "isBundle",
    "lifecycleStatus", "name", "relatedParty", "specCharacteristic",
    "targetEntitySchema", "validFor", "version",
}

# TMF662: POST /entityCatalog mandatory attributes: name
MANDATORY_ON_CREATE = {"name"}  # :contentReference[oaicite:4]{index=4}

# TMF662: PATCHable fields for EntityCatalog
PATCHABLE_FIELDS = {
    "category", "description", "lifecycleStatus", "name", "relatedParty", "validFor", "version"
}  # :contentReference[oaicite:5]{index=5}


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _error(status, reason, code=None, details=None):
    payload = {"error": {"status": status, "reason": reason}}
    if code:
        payload["error"]["code"] = code
    if details:
        payload["error"]["details"] = details
    return _json_response(payload, status=status)


def _parse_json_body():
    try:
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw or "{}")
    except Exception:
        return None


def _now_utc_dt():
    # Odoo fields.Datetime expects naive datetimes
    return datetime.utcnow()



def _apply_fields_param(obj: dict, fields_param):
    # TMF attribute selection: fields=... (first level) :contentReference[oaicite:6]{index=6}
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in wanted or k.startswith("@") or k in ("id", "href")}

def _apply_fields(obj: dict, fields_param):
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in wanted or k in ("id", "href") or k.startswith("@")}


class TMF662EntitySpecificationController(http.Controller):

    # --- LIST (and filtering) ---
    @http.route([BASE_ES, BASE_ES.replace("/entitySpecification", "/EntitySpecification")],
                type="http", auth="public", methods=["GET"], csrf=False)
    def list_entity_specification(self, **params):
        domain = []

        # Filter by id, name, lastUpdate (CTK uses these)
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        if params.get("lastUpdate"):
            try:
                raw = params["lastUpdate"].strip('"')
                dt = parser.isoparse(raw)
                if "T" in raw:
                    start = dt.replace(tzinfo=None, microsecond=0)
                    end = start + timedelta(seconds=1)
                else:
                    start = dt.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
                    end = start + timedelta(days=1)
                domain.append(("last_update", ">=", start))
                domain.append(("last_update", "<", end))
            except Exception:
                # If parse fails, return empty rather than 500
                domain.append(("id", "=", 0))

        recs = request.env["tmf.entity.specification"].sudo().search(domain)
        out = []
        for r in recs:
            payload = _apply_fields(r.to_tmf_json(), params.get("fields"))
            out.append(payload)
        return _json_response(out, status=200)

    # --- RETRIEVE ---
    @http.route([f"{BASE_ES}/<string:rid>", f"{API_BASE}/EntitySpecification/<string:rid>"],
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_entity_specification(self, rid, **params):
        rec = request.env["tmf.entity.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"{RESOURCE_ES} {rid} not found")
        payload = _apply_fields(rec.to_tmf_json(), params.get("fields"))
        return _json_response(payload, status=200)

    # --- CREATE ---
    @http.route([BASE_ES, BASE_ES.replace("/entitySpecification", "/EntitySpecification")],
            type="http", auth="public", methods=["POST"], csrf=False)
    def create_entity_specification(self, **params):
        try:
            data = _parse_json_body()
            if data is None:
                return _error(400, "Invalid JSON body")

            if not data.get("name"):
                return _error(400, "Missing mandatory attribute(s)", details={"missing": ["name"]})

            model = request.env["tmf.entity.specification"].sudo()

            # ✅ if your model has tmf_from_json, use it
            if hasattr(model, "tmf_from_json"):
                vals = model.tmf_from_json(data, for_patch=False)
            else:
                # ✅ fallback mapping so CTK can proceed
                vals = {
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "version": data.get("version"),
                    "lifecycle_status": data.get("lifecycleStatus"),
                }

            # ✅ always server-manage lastUpdate
            vals["last_update"] = _now_utc_dt()

            # ✅ ensure tmf_id exists if your mixin doesn't set it
            if "tmf_id" not in vals:
                import uuid
                vals["tmf_id"] = str(uuid.uuid4())

            rec = model.create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        except Exception as e:
            request.env.cr.rollback()
            return _error(500, "Internal error on create entitySpecification", details=str(e))

    # --- PATCH ---
    @http.route([f"{BASE_ES}/<string:rid>", f"{API_BASE}/EntitySpecification/<string:rid>"],
                type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_entity_specification(self, rid, **params):
        rec = request.env["tmf.entity.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"{RESOURCE_ES} {rid} not found")

        ct = (request.httprequest.content_type or "").lower()
        if "merge-patch+json" not in ct and "application/json" not in ct:
            return _error(415, "Unsupported Content-Type. Use application/merge-patch+json")

        patch = _parse_json_body()
        if patch is None:
            return _error(400, "Invalid JSON body")

        illegal = [k for k in patch.keys() if k not in ES_PATCHABLE]
        if illegal:
            return _error(400, "Non patchable attribute(s) present",
                          details={"nonPatchable": illegal, "allowed": sorted(ES_PATCHABLE)})

        vals = rec.tmf_from_json(patch, for_patch=True)
        vals["last_update"] = _now_utc_dt()   # ✅ FIX
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    # --- DELETE ---
    @http.route([f"{BASE_ES}/<string:rid>", f"{API_BASE}/EntitySpecification/<string:rid>"],
                type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_entity_specification(self, rid, **params):
        rec = request.env["tmf.entity.specification"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"{RESOURCE_ES} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

class TMF662EntityCatalogController(http.Controller):

    # --------
    # LIST
    # --------
    @http.route([BASE_PATH, BASE_PATH.replace("/entityCatalog", "/EntityCatalog")],
            type="http", auth="public", methods=["GET"], csrf=False)
    def list_entity_catalog(self, **params):
        domain = []

        # Minimal filtering support (name, lifecycleStatus) as a practical baseline.
        # TMF says filtering "may be available depending on compliance level". :contentReference[oaicite:7]{index=7}
        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))
        if params.get("lifecycleStatus"):
            domain.append(("lifecycle_status", "=", params["lifecycleStatus"]))

        limit = int(params.get("limit") or 0) or None
        offset = int(params.get("offset") or 0) or 0

        env = request.env["tmf.entity.catalog"].sudo()
        records = env.search(domain, limit=limit, offset=offset)
        total = env.search_count(domain)
        result = []
        for r in records:
            payload = r.to_tmf_json()
            payload = _apply_fields_param(payload, params.get("fields"))
            result.append(payload)
        headers = [
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(result))),
        ]
        return _json_response(result, status=200, headers=headers)

    # --------
    # RETRIEVE
    # --------
    @http.route([f"{BASE_PATH}/<string:rid>", f"{API_BASE}/EntityCatalog/<string:rid>"],
            type="http", auth="public", methods=["GET"], csrf=False)
    def get_entity_catalog(self, rid, **params):
        rec = request.env["tmf.entity.catalog"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"{RESOURCE} {rid} not found")
        payload = rec.to_tmf_json()
        payload = _apply_fields_param(payload, params.get("fields"))
        return _json_response(payload, status=200)

    # --------
    # CREATE
    # --------
    @http.route([BASE_PATH, BASE_PATH.replace("/entityCatalog", "/EntityCatalog")],
            type="http", auth="public", methods=["POST"], csrf=False)
    def create_entity_catalog(self, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        missing = [k for k in MANDATORY_ON_CREATE if not data.get(k)]
        if missing:
            return _error(400, "Missing mandatory attribute(s)", details={"missing": missing})

        vals = request.env["tmf.entity.catalog"].sudo().tmf_from_json(data, for_patch=False)
        # server-managed lastUpdate
        vals["last_update"] = _now_utc_dt()

        rec = request.env["tmf.entity.catalog"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    # --------
    # PATCH (merge-patch required)
    # --------
    @http.route([f"{BASE_PATH}/<string:rid>", f"{API_BASE}/EntityCatalog/<string:rid>"],
            type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_entity_catalog(self, rid, **params):
        rec = request.env["tmf.entity.catalog"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"{RESOURCE} {rid} not found")

        ct = (request.httprequest.content_type or "").lower()
        if "merge-patch+json" not in ct and "application/json" not in ct:
            # TMF662: merge-patch mandatory :contentReference[oaicite:8]{index=8}
            return _error(
                415,
                "Unsupported Content-Type. Use application/merge-patch+json",
                details={"contentType": request.httprequest.content_type},
            )

        patch = _parse_json_body()
        if patch is None:
            return _error(400, "Invalid JSON body")

        # Enforce patchable attributes
        illegal = [k for k in patch.keys() if k not in PATCHABLE_FIELDS]
        if illegal:
            return _error(
                400,
                "Non patchable attribute(s) present",
                details={"nonPatchable": illegal, "allowed": sorted(PATCHABLE_FIELDS)},
            )

        vals = rec.tmf_from_json(patch, for_patch=True)
        vals["last_update"] = _now_utc_dt()
        rec.write(vals)

        return _json_response(rec.to_tmf_json(), status=200)

    # --------
    # DELETE
    # --------
    @http.route([f"{BASE_PATH}/<string:rid>", f"{API_BASE}/EntityCatalog/<string:rid>"],
            type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_entity_catalog(self, rid, **params):
        rec = request.env["tmf.entity.catalog"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"{RESOURCE} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)
