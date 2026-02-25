import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/costManagement/v5"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "actualCost": {
        "model": "tmf.actual.cost",
        "path": f"{API_BASE}/actualCost",
        "required": ["actualCostItem"],
        "type": "ActualCost",
        "item_key": "actualCostItem",
        "item_type": "ActualCostItem",
    },
    "projectedCost": {
        "model": "tmf.projected.cost",
        "path": f"{API_BASE}/projectedCost",
        "required": ["projectedCostItem"],
        "type": "ProjectedCost",
        "item_key": "projectedCostItem",
        "item_type": "ProjectedCostItem",
    },
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
    wanted |= {"id", "href", "@type"}
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
    query = (query or "").lower()
    if "projectedcost" in query:
        return "projectedCost"
    return "actualCost"


class TMF764Controller(http.Controller):
    def _list(self, api_name, **params):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
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
        data.setdefault("@type", cfg["type"])
        data.setdefault("state", "acknowledged")
        items = data.get(cfg["item_key"]) or []
        for idx, item in enumerate(items):
            if isinstance(item, dict):
                item.setdefault("@type", cfg["item_type"])
                item.setdefault("id", item.get("id") or f"{idx + 1:02d}")

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

    @http.route([RESOURCES["actualCost"]["path"], f"{API_BASE}/ActualCost"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_actual_cost(self, **params):
        return self._list("actualCost", **params)

    @http.route([RESOURCES["actualCost"]["path"], f"{API_BASE}/ActualCost"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_actual_cost(self, **_params):
        return self._create("actualCost")

    @http.route([f"{RESOURCES['actualCost']['path']}/<string:rid>", f"{API_BASE}/ActualCost/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_actual_cost(self, rid, **params):
        return self._get("actualCost", rid, **params)

    @http.route([f"{RESOURCES['actualCost']['path']}/<string:rid>", f"{API_BASE}/ActualCost/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_actual_cost(self, rid, **_params):
        return self._patch("actualCost", rid)

    @http.route([f"{RESOURCES['actualCost']['path']}/<string:rid>", f"{API_BASE}/ActualCost/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_actual_cost(self, rid, **_params):
        return self._delete("actualCost", rid)

    @http.route([RESOURCES["projectedCost"]["path"], f"{API_BASE}/ProjectedCost"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_projected_cost(self, **params):
        return self._list("projectedCost", **params)

    @http.route([RESOURCES["projectedCost"]["path"], f"{API_BASE}/ProjectedCost"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_projected_cost(self, **_params):
        return self._create("projectedCost")

    @http.route([f"{RESOURCES['projectedCost']['path']}/<string:rid>", f"{API_BASE}/ProjectedCost/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_projected_cost(self, rid, **params):
        return self._get("projectedCost", rid, **params)

    @http.route([f"{RESOURCES['projectedCost']['path']}/<string:rid>", f"{API_BASE}/ProjectedCost/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_projected_cost(self, rid, **_params):
        return self._patch("projectedCost", rid)

    @http.route([f"{RESOURCES['projectedCost']['path']}/<string:rid>", f"{API_BASE}/ProjectedCost/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_projected_cost(self, rid, **_params):
        return self._delete("projectedCost", rid)

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
                "name": f"tmf764-{api_name}-{callback}",
                "api_name": api_name,
                "callback": callback,
                "query": query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name not in RESOURCES:
            return _error(404, f"Hub subscription {sid} not found")
        return _json_response(_subscription_json(rec), status=200)

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
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/listener/actualCostCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_actual_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/actualCostAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_actual_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/actualCostStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_actual_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/actualCostDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_actual_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/projectedCostCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_projected_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/projectedCostAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_projected_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/projectedCostStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_projected_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/projectedCostDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_projected_delete(self, **_params):
        return self._listener_ok()

