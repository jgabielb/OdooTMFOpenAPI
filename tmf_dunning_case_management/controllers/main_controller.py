import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/dunningCase/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "dunningScenario": {
        "model": "tmf.dunning.scenario",
        "path": f"{API_BASE}/dunningScenario",
        "alt_path": f"{API_BASE}/DunningScenario",
        "required": ["name", "dunningRule"],
    },
    "dunningRule": {
        "model": "tmf.dunning.rule",
        "path": f"{API_BASE}/dunningRule",
        "alt_path": f"{API_BASE}/DunningRule",
        "required": ["dunningEvent", "dunningAction"],
    },
    "dunningCase": {
        "model": "tmf.dunning.case",
        "path": f"{API_BASE}/dunningCase",
        "alt_path": f"{API_BASE}/DunningCase",
        "required": ["dunningScenario", "dunningCaseRule", "billingAccount"],
    },
}

FILTER_MAP = {
    "dunningScenario": {"id": "tmf_id", "name": "name", "category": "category"},
    "dunningRule": {"id": "tmf_id", "name": "name", "dunningEvent": "dunning_event", "dunningAction": "dunning_action"},
    "dunningCase": {"id": "tmf_id", "status": "status", "category": "category"},
}


def _json_response(payload, status=200, headers=None):
    response_headers = [("Content-Type", "application/json")]
    if headers:
        response_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=response_headers, status=status)


def _error(status, reason):
    code = str(status)
    return _json_response({"code": code, "status": code, "reason": reason}, status=status)


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


def _find_record(model_name, rid):
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
    return {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}


def _guess_api_name(query):
    q = (query or "").lower()
    if "dunningrule" in q:
        return "dunningRule"
    if "dunningscenario" in q:
        return "dunningScenario"
    return "dunningCase"


class TMF728Controller(http.Controller):
    def _domain_from_params(self, api_name, params):
        domain = []
        for param_name, field_name in FILTER_MAP[api_name].items():
            if params.get(param_name):
                domain.append((field_name, "=", params[param_name]))
        return domain

    def _list(self, api_name, **params):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        domain = self._domain_from_params(api_name, params)
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _create(self, api_name):
        cfg = RESOURCES[api_name]
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        for required in cfg["required"]:
            if required not in data:
                return _error(400, f"Missing mandatory attribute: {required}")
        vals = request.env[cfg["model"]].sudo().from_tmf_json(data)
        rec = request.env[cfg["model"]].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    def _get(self, api_name, rid, **params):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    def _patch(self, api_name, rid):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        vals = request.env[cfg["model"]].sudo().from_tmf_json(patch, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    def _delete(self, api_name, rid):
        cfg = RESOURCES[api_name]
        rec = _find_record(cfg["model"], rid)
        if not rec:
            return _error(404, f"{api_name} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route([RESOURCES["dunningScenario"]["path"], RESOURCES["dunningScenario"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_dunning_scenario(self, **params):
        return self._list("dunningScenario", **params)

    @http.route([RESOURCES["dunningScenario"]["path"], RESOURCES["dunningScenario"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_dunning_scenario(self, **_params):
        return self._create("dunningScenario")

    @http.route([f"{RESOURCES['dunningScenario']['path']}/<string:rid>", f"{RESOURCES['dunningScenario']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_dunning_scenario(self, rid, **params):
        return self._get("dunningScenario", rid, **params)

    @http.route([f"{RESOURCES['dunningScenario']['path']}/<string:rid>", f"{RESOURCES['dunningScenario']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_dunning_scenario(self, rid, **_params):
        return self._patch("dunningScenario", rid)

    @http.route([f"{RESOURCES['dunningScenario']['path']}/<string:rid>", f"{RESOURCES['dunningScenario']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_dunning_scenario(self, rid, **_params):
        return self._delete("dunningScenario", rid)

    @http.route([RESOURCES["dunningRule"]["path"], RESOURCES["dunningRule"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_dunning_rule(self, **params):
        return self._list("dunningRule", **params)

    @http.route([RESOURCES["dunningRule"]["path"], RESOURCES["dunningRule"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_dunning_rule(self, **_params):
        return self._create("dunningRule")

    @http.route([f"{RESOURCES['dunningRule']['path']}/<string:rid>", f"{RESOURCES['dunningRule']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_dunning_rule(self, rid, **params):
        return self._get("dunningRule", rid, **params)

    @http.route([f"{RESOURCES['dunningRule']['path']}/<string:rid>", f"{RESOURCES['dunningRule']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_dunning_rule(self, rid, **_params):
        return self._patch("dunningRule", rid)

    @http.route([f"{RESOURCES['dunningRule']['path']}/<string:rid>", f"{RESOURCES['dunningRule']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_dunning_rule(self, rid, **_params):
        return self._delete("dunningRule", rid)

    @http.route([RESOURCES["dunningCase"]["path"], RESOURCES["dunningCase"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_dunning_case(self, **params):
        return self._list("dunningCase", **params)

    @http.route([RESOURCES["dunningCase"]["path"], RESOURCES["dunningCase"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_dunning_case(self, **_params):
        return self._create("dunningCase")

    @http.route([f"{RESOURCES['dunningCase']['path']}/<string:rid>", f"{RESOURCES['dunningCase']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_dunning_case(self, rid, **params):
        return self._get("dunningCase", rid, **params)

    @http.route([f"{RESOURCES['dunningCase']['path']}/<string:rid>", f"{RESOURCES['dunningCase']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_dunning_case(self, rid, **_params):
        return self._patch("dunningCase", rid)

    @http.route([f"{RESOURCES['dunningCase']['path']}/<string:rid>", f"{RESOURCES['dunningCase']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_dunning_case(self, rid, **_params):
        return self._delete("dunningCase", rid)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        query = data.get("query", "") or ""
        api_name = _guess_api_name(query)
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf728-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/dunningCaseCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_dunning_case_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/dunningCaseStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_dunning_case_state_change(self, **_params):
        return self._listener_ok()

