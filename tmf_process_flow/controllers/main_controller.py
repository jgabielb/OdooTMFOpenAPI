import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/processFlowManagement/v4"

RESOURCE_SPECS = {
    "processFlowSpecification": {
        "model": "tmf.process.flow.specification",
        "required": ["name"],
        "map": {
            "name": "name",
            "state": "state",
            "description": "description",
            "processFlowDate": "process_flow_date",
            "channel": "channel",
            "characteristic": "characteristic",
            "relatedEntity": "related_entity",
            "relatedParty": "related_party",
        },
    },
    "taskFlowSpecification": {
        "model": "tmf.task.flow.specification",
        "required": ["name"],
        "map": {
            "name": "name",
            "state": "state",
            "description": "description",
            "processFlowDate": "process_flow_date",
            "channel": "channel",
            "characteristic": "characteristic",
            "relatedEntity": "related_entity",
            "relatedParty": "related_party",
        },
    },
    "processFlow": {
        "model": "tmf.process.flow",
        "required": [],
        "map": {
            "name": "name",
            "state": "state",
            "description": "description",
            "processFlowDate": "process_flow_date",
            "channel": "channel",
            "characteristic": "characteristic",
            "relatedEntity": "related_entity",
            "relatedParty": "related_party",
            "processFlowSpecificationRef": "process_flow_specification_ref",
        },
    },
}


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
    return {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}


def _build_vals(spec, data):
    vals = {}
    for tmf_key, odoo_field in spec["map"].items():
        if tmf_key in data:
            vals[odoo_field] = data.get(tmf_key)
    vals["extra_json"] = {k: v for k, v in data.items() if k not in set(spec["map"].keys()) | {"id", "href"}}
    return vals


class TMF701ProcessFlowController(http.Controller):
    def _list_resource(self, key, **params):
        spec = RESOURCE_SPECS[key]
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env[spec["model"]].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    def _create_resource(self, key, **_params):
        spec = RESOURCE_SPECS[key]
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        missing = [k for k in spec["required"] if data.get(k) in (None, "", [], {})]
        if missing:
            return _error(400, f"Missing mandatory attribute(s): {', '.join(missing)}")
        rec = request.env[spec["model"]].sudo().create(_build_vals(spec, data))
        return _json_response(rec.to_tmf_json(), status=201)

    def _get_resource(self, key, rid, **params):
        spec = RESOURCE_SPECS[key]
        rec = _find_by_rid(spec["model"], rid)
        if not rec:
            return _error(404, f"{key} {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    def _delete_resource(self, key, rid, **_params):
        spec = RESOURCE_SPECS[key]
        rec = _find_by_rid(spec["model"], rid)
        if not rec:
            return _error(404, f"{key} {rid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _patch_resource(self, key, rid, **_params):
        spec = RESOURCE_SPECS[key]
        rec = _find_by_rid(spec["model"], rid)
        if not rec:
            return _error(404, f"{key} {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        rec.sudo().write(_build_vals(spec, patch))
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/processFlowSpecification", type="http", auth="public", methods=["GET"], csrf=False)
    def list_process_flow_specification(self, **params):
        return self._list_resource("processFlowSpecification", **params)

    @http.route(f"{API_BASE}/processFlowSpecification", type="http", auth="public", methods=["POST"], csrf=False)
    def create_process_flow_specification(self, **params):
        return self._create_resource("processFlowSpecification", **params)

    @http.route(f"{API_BASE}/processFlowSpecification/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_process_flow_specification(self, rid, **params):
        return self._get_resource("processFlowSpecification", rid, **params)

    @http.route(f"{API_BASE}/processFlowSpecification/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_process_flow_specification(self, rid, **params):
        return self._delete_resource("processFlowSpecification", rid, **params)

    @http.route(f"{API_BASE}/processFlowSpecification/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_process_flow_specification(self, rid, **params):
        return self._patch_resource("processFlowSpecification", rid, **params)

    @http.route(f"{API_BASE}/taskFlowSpecification", type="http", auth="public", methods=["GET"], csrf=False)
    def list_task_flow_specification(self, **params):
        return self._list_resource("taskFlowSpecification", **params)

    @http.route(f"{API_BASE}/taskFlowSpecification", type="http", auth="public", methods=["POST"], csrf=False)
    def create_task_flow_specification(self, **params):
        return self._create_resource("taskFlowSpecification", **params)

    @http.route(f"{API_BASE}/taskFlowSpecification/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_task_flow_specification(self, rid, **params):
        return self._get_resource("taskFlowSpecification", rid, **params)

    @http.route(f"{API_BASE}/taskFlowSpecification/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_task_flow_specification(self, rid, **params):
        return self._delete_resource("taskFlowSpecification", rid, **params)

    @http.route(f"{API_BASE}/taskFlowSpecification/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_task_flow_specification(self, rid, **params):
        return self._patch_resource("taskFlowSpecification", rid, **params)

    @http.route(f"{API_BASE}/processFlow", type="http", auth="public", methods=["GET"], csrf=False)
    def list_process_flow(self, **params):
        return self._list_resource("processFlow", **params)

    @http.route(f"{API_BASE}/processFlow", type="http", auth="public", methods=["POST"], csrf=False)
    def create_process_flow(self, **params):
        return self._create_resource("processFlow", **params)

    @http.route(f"{API_BASE}/processFlow/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_process_flow(self, rid, **params):
        return self._get_resource("processFlow", rid, **params)

    @http.route(f"{API_BASE}/processFlow/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_process_flow(self, rid, **params):
        return self._delete_resource("processFlow", rid, **params)

    @http.route(f"{API_BASE}/processFlow/<string:process_flow_id>/taskFlow", type="http", auth="public", methods=["GET"], csrf=False)
    def list_task_flow(self, process_flow_id, **params):
        process_flow = _find_by_rid("tmf.process.flow", process_flow_id)
        if not process_flow:
            return _error(404, f"processFlow {process_flow_id} not found")
        domain = [("process_flow_id", "=", process_flow.id)]
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.task.flow"].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/processFlow/<string:process_flow_id>/taskFlow", type="http", auth="public", methods=["POST"], csrf=False)
    def create_task_flow(self, process_flow_id, **_params):
        process_flow = _find_by_rid("tmf.process.flow", process_flow_id)
        if not process_flow:
            return _error(404, f"processFlow {process_flow_id} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        vals = {
            "process_flow_id": process_flow.id,
            "name": data.get("name"),
            "state": data.get("state"),
            "description": data.get("description"),
            "process_flow_date": data.get("processFlowDate"),
            "channel": data.get("channel") or [],
            "characteristic": data.get("characteristic") or [],
            "related_entity": data.get("relatedEntity") or [],
            "related_party": data.get("relatedParty") or [],
            "task_flow_specification_ref": data.get("taskFlowSpecificationRef") or {},
            "information_required": bool(data.get("informationRequired", False)),
            "extra_json": {
                k: v
                for k, v in data.items()
                if k
                not in {
                    "name",
                    "state",
                    "description",
                    "processFlowDate",
                    "channel",
                    "characteristic",
                    "relatedEntity",
                    "relatedParty",
                    "taskFlowSpecificationRef",
                    "informationRequired",
                    "id",
                    "href",
                }
            },
        }
        rec = request.env["tmf.task.flow"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(
        f"{API_BASE}/processFlow/<string:process_flow_id>/taskFlow/<string:rid>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_task_flow(self, process_flow_id, rid, **params):
        process_flow = _find_by_rid("tmf.process.flow", process_flow_id)
        if not process_flow:
            return _error(404, f"processFlow {process_flow_id} not found")
        rec = _find_by_rid("tmf.task.flow", rid)
        if not rec or rec.process_flow_id.id != process_flow.id:
            return _error(404, f"taskFlow {rid} not found on processFlow {process_flow_id}")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(
        f"{API_BASE}/processFlow/<string:process_flow_id>/taskFlow/<string:rid>",
        type="http",
        auth="public",
        methods=["PATCH"],
        csrf=False,
    )
    def patch_task_flow(self, process_flow_id, rid, **_params):
        process_flow = _find_by_rid("tmf.process.flow", process_flow_id)
        if not process_flow:
            return _error(404, f"processFlow {process_flow_id} not found")
        rec = _find_by_rid("tmf.task.flow", rid)
        if not rec or rec.process_flow_id.id != process_flow.id:
            return _error(404, f"taskFlow {rid} not found on processFlow {process_flow_id}")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        vals = {
            "name": patch.get("name") if "name" in patch else rec.name,
            "state": patch.get("state") if "state" in patch else rec.state,
            "description": patch.get("description") if "description" in patch else rec.description,
            "process_flow_date": patch.get("processFlowDate") if "processFlowDate" in patch else rec.process_flow_date,
            "channel": patch.get("channel") if "channel" in patch else rec.channel,
            "characteristic": patch.get("characteristic") if "characteristic" in patch else rec.characteristic,
            "related_entity": patch.get("relatedEntity") if "relatedEntity" in patch else rec.related_entity,
            "related_party": patch.get("relatedParty") if "relatedParty" in patch else rec.related_party,
            "task_flow_specification_ref": patch.get("taskFlowSpecificationRef")
            if "taskFlowSpecificationRef" in patch
            else rec.task_flow_specification_ref,
            "information_required": bool(patch.get("informationRequired", rec.information_required)),
        }
        extra = rec.extra_json.copy() if isinstance(rec.extra_json, dict) else {}
        for k, v in patch.items():
            if k not in {
                "name",
                "state",
                "description",
                "processFlowDate",
                "channel",
                "characteristic",
                "relatedEntity",
                "relatedParty",
                "taskFlowSpecificationRef",
                "informationRequired",
                "id",
                "href",
            }:
                extra[k] = v
        vals["extra_json"] = extra
        rec.sudo().write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

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
                "name": f"tmf701-processflow-{callback}",
                "api_name": "processFlow",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists():
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    def _listener_ok(self):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/processFlowSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_spec_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_spec_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_spec_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_spec_attr(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_spec_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_spec_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_spec_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_spec_attr(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/processFlowAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_process_flow_attr(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_attr(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/taskFlowInformationRequiredEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_task_flow_information_required(self, **_params):
        return self._listener_ok()
