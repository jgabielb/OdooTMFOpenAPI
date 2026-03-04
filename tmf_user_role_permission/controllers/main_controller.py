# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import json

API_BASE = "/tmf-api/userRolePermissionManagement/v4"
ALT_BASES = ["/userrolepermission/v4"]


# -------------------- helpers --------------------
def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _json_error(status, code, reason, message=None):
    payload = {"code": str(code), "reason": reason}
    if message:
        payload["message"] = message
    return _json_response(payload, status=status)


def _safe(handler):
    try:
        return handler()
    except ValidationError as e:
        return _json_error(400, 400, "Bad Request", str(e))
    except Exception as e:
        # Prevent HTML error pages (Newman JSONError: Unexpected token '<')
        return _json_error(500, 500, "Internal Server Error", str(e))


def _parse_json_body():
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValidationError("Invalid JSON body.")


def _apply_fields_filter(obj, fields_param):
    # fields=... only for first level attributes
    if not fields_param:
        return obj
    wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in wanted}


def _patch_merge(existing_payload, patch_payload):
    merged = dict(existing_payload)
    for k, v in patch_payload.items():
        if v is None:
            merged.pop(k, None)
        else:
            merged[k] = v
    return merged


def _ensure_href(rec, resource_name):
    """
    Ensure href is stored (CTK later filters by href=...).
    resource_name: 'permission' or 'userRole'
    """
    expected = f"{API_BASE}/{resource_name}/{rec.tmf_id}"
    if getattr(rec, "href", None) != expected:
        rec.sudo().write({"href": expected})


# -------------------- controller --------------------
class TMF672Controller(http.Controller):

    # ---------------- Permission ----------------
    @http.route(
        [f"{API_BASE}/permission", f"{API_BASE}/Permission"] + [f"{b}/permission" for b in ALT_BASES] + [f"{b}/Permission" for b in ALT_BASES],
        type="http", auth="public", methods=["GET"], csrf=False
    )
    def list_permission(self, **query):
        return _safe(lambda: self._list_permission_impl(**query))

    def _list_permission_impl(self, **query):
        domain = []

        # CTK filters you MUST support
        tmf_id = query.get("id")
        href = query.get("href")
        if href:
            # only filter if stored field exists (after upgrade it will)
            domain.append(("href", "=", href))
        if tmf_id:
            domain.append(("tmf_id", "=", tmf_id))
        if href:
            domain.append(("href", "=", href))

        # optional filter: user.id=...
        user_id = query.get("user.id")
        if user_id:
            domain.append(("user_json", "ilike", f'"id": "{user_id}"'))

        recs = request.env["tmf672.permission"].sudo().search(domain)
        fields_param = query.get("fields")

        out = []
        for r in recs:
            _ensure_href(r, "permission")
            payload = r.tmf_to_payload(api_base_path=API_BASE)
            out.append(_apply_fields_filter(payload, fields_param))

        return _json_response(out, status=200)

    @http.route(
        [f"{API_BASE}/permission/<string:rid>", f"{API_BASE}/Permission/<string:rid>"]
        + [f"{b}/permission/<string:rid>" for b in ALT_BASES]
        + [f"{b}/Permission/<string:rid>" for b in ALT_BASES],
        type="http", auth="public", methods=["GET"], csrf=False
    )
    def get_permission(self, rid, **query):
        return _safe(lambda: self._get_permission_impl(rid, **query))

    def _get_permission_impl(self, rid, **query):
        rec = request.env["tmf672.permission"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_error(404, 404, "Not Found")

        _ensure_href(rec, "permission")
        payload = rec.tmf_to_payload(api_base_path=API_BASE)
        return _json_response(_apply_fields_filter(payload, query.get("fields")), status=200)

    @http.route(
        [f"{API_BASE}/permission", f"{API_BASE}/Permission"] + [f"{b}/permission" for b in ALT_BASES] + [f"{b}/Permission" for b in ALT_BASES],
        type="http", auth="public", methods=["POST"], csrf=False
    )
    def post_permission(self, **_kw):
        return _safe(lambda: self._post_permission_impl())

    def _post_permission_impl(self):
        payload = _parse_json_body()
        rec = request.env["tmf672.permission"].tmf_create_from_payload(request.env, payload, api_base_path=API_BASE)
        _ensure_href(rec, "permission")
        return _json_response(rec.tmf_to_payload(api_base_path=API_BASE), status=201)

    @http.route(
        [f"{API_BASE}/permission/<string:rid>", f"{API_BASE}/Permission/<string:rid>"]
        + [f"{b}/permission/<string:rid>" for b in ALT_BASES]
        + [f"{b}/Permission/<string:rid>" for b in ALT_BASES],
        type="http", auth="public", methods=["PATCH"], csrf=False
    )
    def patch_permission(self, rid, **_kw):
        return _safe(lambda: self._patch_permission_impl(rid))

    def _patch_permission_impl(self, rid):
        rec = request.env["tmf672.permission"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_error(404, 404, "Not Found")

        patch = _parse_json_body()
        current = rec.tmf_to_payload(api_base_path=API_BASE)
        merged = _patch_merge(current, patch)

        valid_for = merged.get("validFor") or {}
        vals = {
            "tmf_type": merged.get("@type") or rec.tmf_type,
            "base_type": merged.get("@baseType"),
            "schema_location": merged.get("@schemaLocation"),
            "description": merged.get("description"),
            "user_json": json.dumps(merged.get("user"), ensure_ascii=False) if merged.get("user") else rec.user_json,
            "granter_json": json.dumps(merged.get("granter"), ensure_ascii=False) if merged.get("granter") else False,
            "asset_user_role_json": json.dumps(merged.get("assetUserRole"), ensure_ascii=False) if merged.get("assetUserRole") else False,
            "privilege_json": json.dumps(merged.get("privilege"), ensure_ascii=False) if merged.get("privilege") else False,
        }

        # safer datetime parsing
        if valid_for.get("startDateTime"):
            vals["valid_for_start"] = valid_for.get("startDateTime")
        if valid_for.get("endDateTime"):
            vals["valid_for_end"] = valid_for.get("endDateTime")

        rec.write(vals)
        _ensure_href(rec, "permission")
        return _json_response(rec.tmf_to_payload(api_base_path=API_BASE), status=200)

    # ---------------- UserRole ----------------
    @http.route(
        [f"{API_BASE}/userRole", f"{API_BASE}/UserRole"] + [f"{b}/userRole" for b in ALT_BASES] + [f"{b}/UserRole" for b in ALT_BASES],
        type="http", auth="public", methods=["GET"], csrf=False
    )
    def list_user_role(self, **query):
        return _safe(lambda: self._list_user_role_impl(**query))

    def _list_user_role_impl(self, **query):
        domain = []

        # CTK filters you MUST support
        tmf_id = query.get("id")
        href = query.get("href")
        if tmf_id:
            domain.append(("tmf_id", "=", tmf_id))
        if href:
            domain.append(("href", "=", href))

        recs = request.env["tmf672.user.role"].sudo().search(domain)
        fields_param = query.get("fields")

        out = []
        for r in recs:
            _ensure_href(r, "userRole")
            payload = r.tmf_to_payload(api_base_path=API_BASE)
            out.append(_apply_fields_filter(payload, fields_param))

        return _json_response(out, status=200)

    @http.route(
        [f"{API_BASE}/userRole/<string:rid>", f"{API_BASE}/UserRole/<string:rid>"]
        + [f"{b}/userRole/<string:rid>" for b in ALT_BASES]
        + [f"{b}/UserRole/<string:rid>" for b in ALT_BASES],
        type="http", auth="public", methods=["GET"], csrf=False
    )
    def get_user_role(self, rid, **query):
        return _safe(lambda: self._get_user_role_impl(rid, **query))

    def _get_user_role_impl(self, rid, **query):
        rec = request.env["tmf672.user.role"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_error(404, 404, "Not Found")

        _ensure_href(rec, "userRole")
        payload = rec.tmf_to_payload(api_base_path=API_BASE)
        return _json_response(_apply_fields_filter(payload, query.get("fields")), status=200)

    @http.route(
        [f"{API_BASE}/userRole", f"{API_BASE}/UserRole"] + [f"{b}/userRole" for b in ALT_BASES] + [f"{b}/UserRole" for b in ALT_BASES],
        type="http", auth="public", methods=["POST"], csrf=False
    )
    def post_user_role(self, **_kw):
        return _safe(lambda: self._post_user_role_impl())

    def _post_user_role_impl(self):
        payload = _parse_json_body()
        rec = request.env["tmf672.user.role"].tmf_create_from_payload(request.env, payload)
        _ensure_href(rec, "userRole")
        return _json_response(rec.tmf_to_payload(api_base_path=API_BASE), status=201)

    @http.route(
        [f"{API_BASE}/userRole/<string:rid>", f"{API_BASE}/UserRole/<string:rid>"]
        + [f"{b}/userRole/<string:rid>" for b in ALT_BASES]
        + [f"{b}/UserRole/<string:rid>" for b in ALT_BASES],
        type="http", auth="public", methods=["PATCH"], csrf=False
    )
    def patch_user_role(self, rid, **_kw):
        return _safe(lambda: self._patch_user_role_impl(rid))

    def _patch_user_role_impl(self, rid):
        rec = request.env["tmf672.user.role"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _json_error(404, 404, "Not Found")

        patch = _parse_json_body()
        current = rec.tmf_to_payload(api_base_path=API_BASE)
        merged = _patch_merge(current, patch)

        vals = {
            "tmf_type": merged.get("@type") or rec.tmf_type,
            "base_type": merged.get("@baseType"),
            "schema_location": merged.get("@schemaLocation"),
            "involvement_role": merged.get("involvementRole"),
            # IMPORTANT: CTK expects entitlement to be an array always.
            "entitlement_json": json.dumps(merged.get("entitlement"), ensure_ascii=False)
            if merged.get("entitlement") is not None
            else rec.entitlement_json,
        }

        rec.write(vals)
        _ensure_href(rec, "userRole")
        return _json_response(rec.tmf_to_payload(api_base_path=API_BASE), status=200)
