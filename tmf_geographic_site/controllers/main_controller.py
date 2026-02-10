# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import json


API_BASE = "/tmf-api/geographicSiteManagement/v4"
RESOURCE = "geographicSite"


def _json_response(payload, status=200, headers=None):
    hdrs = [("Content-Type", "application/json")]
    if headers:
        hdrs.extend(headers)
    return request.make_response(json.dumps(payload, ensure_ascii=False), status=status, headers=hdrs)


def _error(status, message):
    # Minimal TMF-style error body (keep simple)
    return _json_response({"error": message}, status=status)


class TMFGeographicSiteController(http.Controller):

    # -------------------------
    # GET list: /geographicSite?fields=...&{filtering}
    # -------------------------
    @http.route(f"{API_BASE}/{RESOURCE}", type="http", auth="public", methods=["GET"], csrf=False)
    def list_geographic_sites(self, **params):
        env = request.env["tmf.geographic.site"].sudo()

        # Basic filtering (user guide examples show simple query params like code=Warehouse&state=active)
        domain = []
        if "code" in params:
            domain.append(("code", "=", params["code"]))
        # spec uses "status" field; example shows "state" but resource uses status in payload
        if "status" in params:
            domain.append(("status", "=", params["status"]))
        if "state" in params:
            domain.append(("status", "=", params["state"]))

        records = env.search(domain)

        # Attribute selection (first level) via fields=id,href,name...
        fields_param = params.get("fields")
        wanted = None
        if fields_param:
            wanted = set([f.strip() for f in fields_param.split(",") if f.strip()])

        out = []
        for r in records:
            full = r.to_tmf_json()
            if wanted:
                # Return only requested keys (if present)
                filtered = {k: v for k, v in full.items() if k in wanted}
                out.append(filtered)
            else:
                out.append(full)

        return _json_response(out, status=200)

    # -------------------------
    # GET by id
    # -------------------------
    @http.route(f"{API_BASE}/{RESOURCE}/<string:site_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_geographic_site(self, site_id, **params):
        env = request.env["tmf.geographic.site"].sudo()
        rec = env.search([("tmf_id", "=", site_id)], limit=1)
        if not rec:
            return _error(404, f"GeographicSite '{site_id}' not found")

        payload = rec.to_tmf_json()

        fields_param = params.get("fields")
        if fields_param:
            wanted = set([f.strip() for f in fields_param.split(",") if f.strip()])
            payload = {k: v for k, v in payload.items() if k in wanted}

        return _json_response(payload, status=200)

    # -------------------------
    # POST create
    # -------------------------
    @http.route(f"{API_BASE}/{RESOURCE}", type="http", auth="public", methods=["POST"], csrf=False)
    def create_geographic_site(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")
            env = request.env["tmf.geographic.site"].sudo()

            # Validate per user guide rules
            env._validate_create_payload(data)

            vals = {
                "code": data.get("code"),
                "description": data.get("description"),
                "name": data.get("name") or "GeographicSite",
                "status": data.get("status"),
                "calendar_json": json.dumps(data.get("calendar"), ensure_ascii=False) if data.get("calendar") is not None else None,
                "place_json": json.dumps(data.get("place"), ensure_ascii=False) if data.get("place") is not None else None,
                "related_party_json": json.dumps(data.get("relatedParty"), ensure_ascii=False) if data.get("relatedParty") is not None else None,
                "site_relationship_json": json.dumps(data.get("siteRelationship"), ensure_ascii=False) if data.get("siteRelationship") is not None else None,
            }

            rec = env.create(vals)
            payload = rec.to_tmf_json()

            # Spec expects 201 on create :contentReference[oaicite:7]{index=7}
            # Add Location header
            location = f"{API_BASE}/{RESOURCE}/{rec.tmf_id}"
            return _json_response(payload, status=201, headers=[("Location", location)])

        except ValidationError as ve:
            return _error(400, str(ve))
        except Exception as e:
            return _error(400, str(e))

    # -------------------------
    # PATCH partial update (merge-patch mandatory in guide)
    # -------------------------
    @http.route(f"{API_BASE}/{RESOURCE}/<string:site_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_geographic_site(self, site_id, **params):
        env = request.env["tmf.geographic.site"].sudo()
        rec = env.search([("tmf_id", "=", site_id)], limit=1)
        if not rec:
            return _error(404, f"GeographicSite '{site_id}' not found")

        # Disallow patching id/href per user guide :contentReference[oaicite:8]{index=8}
        try:
            data = json.loads(request.httprequest.data or b"{}")
            if "id" in data or "href" in data:
                return _error(400, "TMF674 PATCH: 'id' and 'href' are non-patchable.")

            vals = {}
            for k in ("code", "description", "name", "status"):
                if k in data:
                    vals[k] = data.get(k)

            if "calendar" in data:
                # If calendar provided, enforce calendar.status for each element
                cal = data.get("calendar")
                if cal is not None:
                    if not isinstance(cal, list):
                        return _error(400, "TMF674 PATCH: 'calendar' must be a list.")
                    for item in cal:
                        if not isinstance(item, dict) or not item.get("status"):
                            return _error(400, "TMF674 PATCH: 'calendar.status' is mandatory when calendar is provided.")
                vals["calendar_json"] = json.dumps(cal, ensure_ascii=False) if cal is not None else None

            if "place" in data:
                vals["place_json"] = json.dumps(data.get("place"), ensure_ascii=False) if data.get("place") is not None else None

            if "relatedParty" in data:
                vals["related_party_json"] = json.dumps(data.get("relatedParty"), ensure_ascii=False) if data.get("relatedParty") is not None else None

            if "siteRelationship" in data:
                vals["site_relationship_json"] = json.dumps(data.get("siteRelationship"), ensure_ascii=False) if data.get("siteRelationship") is not None else None

            rec.write(vals)
            return _json_response(rec.to_tmf_json(), status=200)

        except Exception as e:
            return _error(400, str(e))

    # -------------------------
    # DELETE
    # -------------------------
    @http.route(f"{API_BASE}/{RESOURCE}/<string:site_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_geographic_site(self, site_id, **params):
        env = request.env["tmf.geographic.site"].sudo()
        rec = env.search([("tmf_id", "=", site_id)], limit=1)
        if not rec:
            return _error(404, f"GeographicSite '{site_id}' not found")

        rec.unlink()
        # Spec shows 204 for delete :contentReference[oaicite:9]{index=9}
        return request.make_response("", status=204)
