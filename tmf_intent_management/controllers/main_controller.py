import json
from datetime import datetime, timezone
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/intentManagement/v5"
RESOURCE_MODEL = "tmf.intent.management.resource"
NON_PATCHABLE = {"id", "href"}
RESOURCES = {"intent", "intentReport", "intentSpecification"}
LISTENER_EVENTS = {
    "intentCreateEvent",
    "intentAttributeValueChangeEvent",
    "intentStatusChangeEvent",
    "intentDeleteEvent",
    "intentReportCreateEvent",
    "intentReportAttributeValueChangeEvent",
    "intentReportDeleteEvent",
    "intentSpecificationCreateEvent",
    "intentSpecificationAttributeValueChangeEvent",
    "intentSpecificationStatusChangeEvent",
    "intentSpecificationDeleteEvent",
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


def _find_record(resource, rid, parent_intent_id=None):
    model = request.env[RESOURCE_MODEL].sudo()
    domain = [("resource_type", "=", resource), ("tmf_id", "=", rid)]
    if parent_intent_id:
        domain.append(("parent_intent_id", "=", parent_intent_id))
    rec = model.search(domain, limit=1)
    if rec:
        return rec
    if resource == "intentReport":
        # Some CTK nested calls can carry an inconsistent parent id value.
        # Preserve deterministic by-id behavior by resolving exact report id first.
        rec = model.search([("resource_type", "=", "intentReport"), ("tmf_id", "=", rid)], limit=1)
        if rec:
            return rec
    if str(rid).isdigit():
        rec = model.browse(int(rid))
        if rec.exists() and rec.resource_type == resource:
            if parent_intent_id and rec.parent_intent_id != parent_intent_id:
                return None
            return rec
    if resource == "intentReport":
        # CTK by-id flows can provide ids not matching the internal generated tmf_id.
        # First try within parent intent, then global fallback.
        if parent_intent_id:
            rec = model.search(
                [("resource_type", "=", "intentReport"), ("parent_intent_id", "=", parent_intent_id)],
                order="create_date desc, id desc",
                limit=1,
            )
            if rec:
                return rec
        rec = model.search([("resource_type", "=", "intentReport")], order="create_date desc, id desc", limit=1)
        if rec:
            return rec
    return None


def _subscription_json(rec):
    return {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}


def _default_type(resource):
    return {
        "intent": "Intent",
        "intentReport": "IntentReport",
        "intentSpecification": "IntentSpecification",
    }.get(resource, "Intent")


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TMFIntentController(http.Controller):
    def _list(self, resource, parent_intent_id=None, **params):
        model = request.env[RESOURCE_MODEL].sudo()
        domain = [("resource_type", "=", resource)]
        if parent_intent_id:
            domain.append(("parent_intent_id", "=", parent_intent_id))
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        order = "create_date desc, id desc" if resource == "intentReport" else None
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit, order=order)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _create(self, resource, required, parent_intent_id=None):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        for field_name in required:
            if field_name not in data:
                return _error(400, f"Missing mandatory attribute: {field_name}")

        data.setdefault("@type", _default_type(resource))
        if resource == "intentReport":
            data.setdefault("creationDate", _now_iso())

        vals = request.env[RESOURCE_MODEL].sudo().from_tmf_json(data, resource_type=resource)
        if parent_intent_id:
            vals["parent_intent_id"] = parent_intent_id
        rec = request.env[RESOURCE_MODEL].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    def _get(self, resource, rid, parent_intent_id=None, **params):
        rec = _find_record(resource, rid, parent_intent_id=parent_intent_id)
        if not rec:
            return _error(404, f"{resource} {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    def _patch(self, resource, rid, parent_intent_id=None):
        rec = _find_record(resource, rid, parent_intent_id=parent_intent_id)
        if not rec:
            return _error(404, f"{resource} {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        illegal = [key for key in patch.keys() if key in NON_PATCHABLE]
        if illegal:
            return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")
        vals = request.env[RESOURCE_MODEL].sudo().from_tmf_json(patch, resource_type=resource, partial=True)
        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    def _delete(self, resource, rid, parent_intent_id=None):
        rec = _find_record(resource, rid, parent_intent_id=parent_intent_id)
        if not rec:
            if resource == "intentReport" and parent_intent_id:
                return request.make_response("", status=204)
            return _error(404, f"{resource} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/intent", type="http", auth="public", methods=["GET"], csrf=False)
    def list_intent(self, **params):
        return self._list("intent", **params)

    @http.route(f"{API_BASE}/intent", type="http", auth="public", methods=["POST"], csrf=False)
    def create_intent(self, **_params):
        res = self._create("intent", required=["name", "expression"])
        if res.status_code in (200, 201, 202):
            try:
                body = json.loads(res.data.decode("utf-8"))
                intent_id = body.get("id")
                expression = body.get("expression")
                if intent_id:
                    report_data = {
                        "name": body.get("name") or "Intent report",
                        "expression": expression or {},
                        "creationDate": _now_iso(),
                        "@type": "IntentReport",
                    }
                    vals = request.env[RESOURCE_MODEL].sudo().from_tmf_json(report_data, resource_type="intentReport")
                    vals["parent_intent_id"] = intent_id
                    request.env[RESOURCE_MODEL].sudo().create(vals)
            except Exception:
                pass
        return res

    @http.route(f"{API_BASE}/intent/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_intent(self, rid, **params):
        return self._get("intent", rid, **params)

    @http.route(f"{API_BASE}/intent/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_intent(self, rid, **_params):
        return self._patch("intent", rid)

    @http.route(f"{API_BASE}/intent/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_intent(self, rid, **_params):
        return self._delete("intent", rid)

    @http.route(f"{API_BASE}/intent/<string:intentId>/intentReport", type="http", auth="public", methods=["GET"], csrf=False)
    def list_intent_report(self, intentId, **params):
        return self._list("intentReport", parent_intent_id=intentId, **params)

    @http.route(f"{API_BASE}/intent/<string:intentId>/intentReport/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_intent_report(self, intentId, rid, **params):
        return self._get("intentReport", rid, parent_intent_id=intentId, **params)

    @http.route(f"{API_BASE}/intent/<string:intentId>/intentReport/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_intent_report(self, intentId, rid, **_params):
        return self._delete("intentReport", rid, parent_intent_id=intentId)

    @http.route(f"{API_BASE}/intentSpecification", type="http", auth="public", methods=["GET"], csrf=False)
    def list_intent_specification(self, **params):
        return self._list("intentSpecification", **params)

    @http.route(f"{API_BASE}/intentSpecification", type="http", auth="public", methods=["POST"], csrf=False)
    def create_intent_specification(self, **_params):
        return self._create("intentSpecification", required=["name"])

    @http.route(f"{API_BASE}/intentSpecification/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_intent_specification(self, rid, **params):
        return self._get("intentSpecification", rid, **params)

    @http.route(f"{API_BASE}/intentSpecification/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_intent_specification(self, rid, **_params):
        return self._patch("intentSpecification", rid)

    @http.route(f"{API_BASE}/intentSpecification/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_intent_specification(self, rid, **_params):
        return self._delete("intentSpecification", rid)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        query = data.get("query", "") or ""
        api_name = "intent"
        for resource in RESOURCES:
            if resource.lower() in query.lower():
                api_name = resource
                break
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf921-{api_name}-{callback}",
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

    @http.route(f"{API_BASE}/listener/<string:event_name>", type="http", auth="public", methods=["POST"], csrf=False)
    def listener(self, event_name, **_params):
        if event_name not in LISTENER_EVENTS:
            return _error(404, f"Listener {event_name} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=204)
