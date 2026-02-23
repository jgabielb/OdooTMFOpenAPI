import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/federatedIdentity/v5"


def _json_response(payload, status=200, headers=None):
    base_headers = [("Content-Type", "application/json")]
    if headers:
        base_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=base_headers, status=status)


def _error(status, reason):
    status_str = str(status)
    return _json_response({"error": {"code": status_str, "status": status_str, "reason": reason}}, status=status)


def _parse_json():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _fields_filter(payload, fields_csv):
    if not fields_csv:
        return payload
    wanted = {item.strip() for item in str(fields_csv).split(",") if item.strip()}
    if not wanted:
        return payload
    wanted |= {"id", "href"}
    return {key: value for key, value in payload.items() if key in wanted}


def _find_by_rid(model_name, rid):
    model = request.env[model_name].sudo()
    rec = model.search([("tmf_id", "=", rid)], limit=1)
    if rec:
        return rec
    if str(rid).isdigit():
        rec = model.browse(int(rid))
        if rec.exists():
            return rec
    return None


def _subscription_json(rec):
    base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
    href = f"{base_url}{API_BASE}/hub/{rec.id}"
    return {
        "id": str(rec.id),
        "href": href,
        "callback": rec.callback,
        "query": rec.query or "",
        "@type": "Hub",
    }


def _require_authorization():
    auth = request.httprequest.headers.get("Authorization")
    if not auth:
        return None, _error(401, "Missing Authorization header")
    return auth, None


class TMF691UserinfoController(http.Controller):
    @http.route(f"{API_BASE}/userinfo", type="http", auth="public", methods=["GET"], csrf=False)
    def list_userinfo(self, **params):
        _auth, err = _require_authorization()
        if err:
            return err
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.userinfo"].sudo()
        total = model.search_count([])
        recs = model.search([], offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/userinfo/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_userinfo(self, rid, **params):
        _auth, err = _require_authorization()
        if err:
            return err
        rec = _find_by_rid("tmf.userinfo", rid)
        if not rec:
            return _error(404, f"Userinfo {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf691-userinfo-{callback}",
                "api_name": "userinfo",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_listener(self, sid, **params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "userinfo":
            return _error(404, f"Hub subscription {sid} not found")
        return _json_response(_fields_filter(_subscription_json(rec), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "userinfo":
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)
