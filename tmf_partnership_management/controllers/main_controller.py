# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import uuid


API_BASE = "/tmf-api/partnershipManagement/v4"

PS_RESOURCE = "partnershipSpecification"
P_RESOURCE = "partnership"


# -------------------------
# Helpers
# -------------------------
def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=headers,
        status=status,
    )


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
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON body: {e}")


def _make_href(resource, tmf_id):
    return f"{API_BASE}/{resource}/{tmf_id}"


def _ensure_str_id(value):
    if value is None:
        return None
    return str(value).strip()


def _merge_patch(target, patch):
    """
    RFC7386 - JSON Merge Patch
    - If patch value is null => remove key
    - Objects are recursively merged
    - Non-objects replace target
    """
    if not isinstance(patch, dict):
        return patch

    if not isinstance(target, dict):
        target = {}

    result = dict(target)
    for k, v in patch.items():
        if v is None:
            if k in result:
                result.pop(k, None)
        else:
            if isinstance(v, dict):
                result[k] = _merge_patch(result.get(k), v)
            else:
                result[k] = v
    return result


def _get_content_type():
    return (request.httprequest.headers.get("Content-Type") or "").split(";")[0].strip().lower()


def _require_merge_patch():
    ct = _get_content_type()
    if ct != "application/merge-patch+json":
        raise ValueError("PATCH requires Content-Type: application/merge-patch+json")


def _pick_fields(obj, fields_param):
    """
    TMF 'fields' is optional; keep simple: if fields present, return only those top-level keys.
    Always keep 'id' and 'href' if present to help clients.
    """
    if not fields_param:
        return obj

    wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
    if not wanted:
        return obj

    out = {}
    for k in wanted:
        if k in obj:
            out[k] = obj[k]

    # keep these if present
    for k in ("id", "href"):
        if k in obj:
            out[k] = obj[k]
    return out


# -------------------------
# Serializers
# -------------------------
def _ps_to_tmf(rec):
    data = {
        "@type": "PartnershipSpecification",
        "id": rec.tmf_id,
        "href": rec.href or _make_href(PS_RESOURCE, rec.tmf_id),
        "name": rec.name,
    }
    if rec.description:
        data["description"] = rec.description
    if rec.role_specification_json:
        try:
            data["roleSpecification"] = json.loads(rec.role_specification_json)
        except Exception:
            # if stored not-json, return as-is string
            data["roleSpecification"] = rec.role_specification_json
    return data


def _p_to_tmf(rec):
    data = {
        "@type": "Partnership",
        "id": rec.tmf_id,
        "href": rec.href or _make_href(P_RESOURCE, rec.tmf_id),
        "name": rec.name,
    }
    if rec.description:
        data["description"] = rec.description

    if rec.specification_json:
        try:
            data["specification"] = json.loads(rec.specification_json)
        except Exception:
            data["specification"] = rec.specification_json

    if rec.partner_json:
        try:
            data["partner"] = json.loads(rec.partner_json)
        except Exception:
            data["partner"] = rec.partner_json

    return data


def _hub_to_tmf(rec):
    return {
        "id": rec.tmf_id,
        "callback": rec.callback,
        "query": rec.query if rec.query else None,
    }


# -------------------------
# Controllers
# -------------------------
class TMF668PartnershipController(http.Controller):

    # -------- PartnershipSpecification --------
    @http.route(f"{API_BASE}/{PS_RESOURCE}", type="http", auth="public", methods=["GET"], csrf=False)
    def list_partnership_specifications(self, **params):
        recs = request.env["tmf.partnership.specification"].sudo().search([])
        items = [_ps_to_tmf(r) for r in recs]
        fields_param = params.get("fields")
        if fields_param:
            items = [_pick_fields(it, fields_param) for it in items]
        return _json_response(items, status=200)

    @http.route(f"{API_BASE}/{PS_RESOURCE}/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_partnership_specification(self, tmf_id, **params):
        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf.partnership.specification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"{PS_RESOURCE} {tmf_id} not found")

        data = _ps_to_tmf(rec)
        fields_param = params.get("fields")
        data = _pick_fields(data, fields_param)
        return _json_response(data, status=200)

    @http.route(f"{API_BASE}/{PS_RESOURCE}", type="http", auth="public", methods=["POST"], csrf=False)
    def create_partnership_specification(self, **_kw):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="TMF668-400", details=str(e))

        name = (body.get("name") or "").strip()
        if not name:
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="Missing mandatory attribute: name")

        tmf_id = _ensure_str_id(body.get("id")) or str(uuid.uuid4())
        href = _make_href(PS_RESOURCE, tmf_id)

        vals = {
            "tmf_id": tmf_id,
            "href": href,
            "name": name,
            "description": body.get("description"),
        }

        if "roleSpecification" in body:
            vals["role_specification_json"] = json.dumps(body.get("roleSpecification"), ensure_ascii=False)

        try:
            rec = request.env["tmf.partnership.specification"].sudo().create(vals)
        except Exception as e:
            return _error(409, "Conflict", code="TMF668-409", details=str(e))

        return _json_response(_ps_to_tmf(rec), status=201, headers=[("Location", href)])

    @http.route(f"{API_BASE}/{PS_RESOURCE}/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_partnership_specification(self, tmf_id, **_kw):
        try:
            _require_merge_patch()
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="TMF668-400", details=str(e))

        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf.partnership.specification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"{PS_RESOURCE} {tmf_id} not found")

        # non patchable
        if "id" in patch or "href" in patch:
            return _error(400, "Bad Request", code="TMF668-NONPATCHABLE", details="id and href are non-patchable")

        current = _ps_to_tmf(rec)
        # convert TMF keys to internal structure before merge
        current_for_merge = {
            "name": current.get("name"),
            "description": current.get("description"),
            "roleSpecification": current.get("roleSpecification"),
        }

        merged = _merge_patch(current_for_merge, patch)

        # validate mandatory still ok (name can be removed by null -> not allowed)
        if "name" in merged and (merged.get("name") is None or str(merged.get("name")).strip() == ""):
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="name cannot be empty")

        vals = {}
        if "name" in merged and merged["name"] is not None:
            vals["name"] = str(merged["name"]).strip()
        if "description" in merged:
            vals["description"] = merged.get("description")
        if "roleSpecification" in merged:
            vals["role_specification_json"] = json.dumps(merged.get("roleSpecification"), ensure_ascii=False)

        try:
            rec.write(vals)
        except Exception as e:
            return _error(409, "Conflict", code="TMF668-409", details=str(e))

        return _json_response(_ps_to_tmf(rec), status=200)

    @http.route(f"{API_BASE}/{PS_RESOURCE}/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_partnership_specification(self, tmf_id, **_kw):
        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf.partnership.specification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"{PS_RESOURCE} {tmf_id} not found")

        rec.unlink()
        return request.make_response("", status=204)

    # -------- Partnership --------
    @http.route(f"{API_BASE}/{P_RESOURCE}", type="http", auth="public", methods=["GET"], csrf=False)
    def list_partnerships(self, **params):
        recs = request.env["tmf.partnership"].sudo().search([])
        items = [_p_to_tmf(r) for r in recs]
        fields_param = params.get("fields")
        if fields_param:
            items = [_pick_fields(it, fields_param) for it in items]
        return _json_response(items, status=200)

    @http.route(f"{API_BASE}/{P_RESOURCE}/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_partnership(self, tmf_id, **params):
        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf.partnership"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"{P_RESOURCE} {tmf_id} not found")

        data = _p_to_tmf(rec)
        fields_param = params.get("fields")
        data = _pick_fields(data, fields_param)
        return _json_response(data, status=200)

    @http.route(f"{API_BASE}/{P_RESOURCE}", type="http", auth="public", methods=["POST"], csrf=False)
    def create_partnership(self, **_kw):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="TMF668-400", details=str(e))

        name = (body.get("name") or "").strip()
        if not name:
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="Missing mandatory attribute: name")

        # mandatory: specification
        if "specification" not in body or body.get("specification") in (None, "", {}):
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="Missing mandatory attribute: specification")

        tmf_id = _ensure_str_id(body.get("id")) or str(uuid.uuid4())
        href = _make_href(P_RESOURCE, tmf_id)

        vals = {
            "tmf_id": tmf_id,
            "href": href,
            "name": name,
            "description": body.get("description"),
            "specification_json": json.dumps(body.get("specification"), ensure_ascii=False),
        }

        if "partner" in body:
            vals["partner_json"] = json.dumps(body.get("partner"), ensure_ascii=False)

        try:
            rec = request.env["tmf.partnership"].sudo().create(vals)
        except Exception as e:
            return _error(409, "Conflict", code="TMF668-409", details=str(e))

        return _json_response(_p_to_tmf(rec), status=201, headers=[("Location", href)])

    @http.route(f"{API_BASE}/{P_RESOURCE}/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_partnership(self, tmf_id, **_kw):
        try:
            _require_merge_patch()
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="TMF668-400", details=str(e))

        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf.partnership"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"{P_RESOURCE} {tmf_id} not found")

        # non patchable
        if "id" in patch or "href" in patch:
            return _error(400, "Bad Request", code="TMF668-NONPATCHABLE", details="id and href are non-patchable")

        current = _p_to_tmf(rec)
        current_for_merge = {
            "name": current.get("name"),
            "description": current.get("description"),
            "specification": current.get("specification"),
            "partner": current.get("partner"),
        }

        merged = _merge_patch(current_for_merge, patch)

        if "name" in merged and (merged.get("name") is None or str(merged.get("name")).strip() == ""):
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="name cannot be empty")

        # specification is mandatory on create, but PATCH can omit it.
        # If PATCH tries to remove it => reject.
        if "specification" in merged and merged.get("specification") in (None, "", {}):
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="specification cannot be removed")

        vals = {}
        if "name" in merged and merged["name"] is not None:
            vals["name"] = str(merged["name"]).strip()
        if "description" in merged:
            vals["description"] = merged.get("description")
        if "specification" in merged:
            vals["specification_json"] = json.dumps(merged.get("specification"), ensure_ascii=False)
        if "partner" in merged:
            vals["partner_json"] = json.dumps(merged.get("partner"), ensure_ascii=False)

        try:
            rec.write(vals)
        except Exception as e:
            return _error(409, "Conflict", code="TMF668-409", details=str(e))

        return _json_response(_p_to_tmf(rec), status=200)

    @http.route(f"{API_BASE}/{P_RESOURCE}/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_partnership(self, tmf_id, **_kw):
        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf.partnership"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"{P_RESOURCE} {tmf_id} not found")

        rec.unlink()
        return request.make_response("", status=204)

    # -------- Hub (Register/Unregister) --------
    # Spec shows POST /hub and DELETE /hub/{id} (and examples show /api/hub) :contentReference[oaicite:6]{index=6}
    # We'll provide both:
    #  - /tmf-api/partnershipManagement/v4/hub
    #  - /hub   (alias)
    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    @http.route("/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_kw):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, "Bad Request", code="TMF668-400", details=str(e))

        callback = (body.get("callback") or "").strip()
        if not callback:
            return _error(400, "Bad Request", code="TMF668-VALIDATION", details="Missing mandatory attribute: callback")

        tmf_id = _ensure_str_id(body.get("id")) or str(uuid.uuid4())
        query = body.get("query")

        try:
            rec = request.env["tmf668.hub.subscription"].sudo().create({
                "tmf_id": tmf_id,
                "callback": callback,
                "query": query,
            })
        except Exception as e:
            return _error(409, "Conflict", code="TMF668-409", details=str(e))

        location = f"{API_BASE}/hub/{rec.tmf_id}"
        return _json_response(_hub_to_tmf(rec), status=201, headers=[("Location", location)])

    @http.route(f"{API_BASE}/hub/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    @http.route("/hub/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, tmf_id, **_kw):
        tmf_id = _ensure_str_id(tmf_id)
        rec = request.env["tmf668.hub.subscription"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not Found", code="TMF668-404", details=f"hub {tmf_id} not found")

        rec.unlink()
        return request.make_response("", status=204)
