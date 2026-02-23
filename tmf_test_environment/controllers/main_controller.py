import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/testEnvironment/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "abstractEnvironment": {
        "model": "tmf.abstract.environment",
        "path": f"{API_BASE}/abstractEnvironment",
        "alt_path": f"{API_BASE}/AbstractEnvironment",
        "required": ["abstractEnvironmentDefinition", "description", "version"],
    },
    "concreteEnvironmentMetaModel": {
        "model": "tmf.concrete.environment.meta.model",
        "path": f"{API_BASE}/concreteEnvironmentMetaModel",
        "alt_path": f"{API_BASE}/ConcreteEnvironmentMetaModel",
        "required": ["concreteEnvironmentMetaModelDefinition", "description", "version"],
    },
    "testResourceAPI": {
        "model": "tmf.test.resource.api",
        "path": f"{API_BASE}/testResourceAPI",
        "alt_path": f"{API_BASE}/TestResourceAPI",
        "required": ["testResourceAPIDefinition", "description", "version"],
    },
    "provisioningArtifact": {
        "model": "tmf.provisioning.artifact",
        "path": f"{API_BASE}/provisioningArtifact",
        "alt_path": f"{API_BASE}/ProvisioningArtifact",
        "required": ["provisioningArtifactDefinition", "description", "version"],
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
    if "concreteenvironmentmetamodel" in q:
        return "concreteEnvironmentMetaModel"
    if "testresourceapi" in q:
        return "testResourceAPI"
    if "provisioningartifact" in q:
        return "provisioningArtifact"
    return "abstractEnvironment"


class TMF705Controller(http.Controller):
    def _list(self, api_name, **params):
        cfg = RESOURCES[api_name]
        model = request.env[cfg["model"]].sudo()
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
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

    @http.route([RESOURCES["abstractEnvironment"]["path"], RESOURCES["abstractEnvironment"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_abstract_environment(self, **params):
        return self._list("abstractEnvironment", **params)

    @http.route([RESOURCES["abstractEnvironment"]["path"], RESOURCES["abstractEnvironment"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_abstract_environment(self, **_params):
        return self._create("abstractEnvironment")

    @http.route([f"{RESOURCES['abstractEnvironment']['path']}/<string:rid>", f"{RESOURCES['abstractEnvironment']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_abstract_environment(self, rid, **params):
        return self._get("abstractEnvironment", rid, **params)

    @http.route([f"{RESOURCES['abstractEnvironment']['path']}/<string:rid>", f"{RESOURCES['abstractEnvironment']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_abstract_environment(self, rid, **_params):
        return self._patch("abstractEnvironment", rid)

    @http.route([f"{RESOURCES['abstractEnvironment']['path']}/<string:rid>", f"{RESOURCES['abstractEnvironment']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_abstract_environment(self, rid, **_params):
        return self._delete("abstractEnvironment", rid)

    @http.route([RESOURCES["concreteEnvironmentMetaModel"]["path"], RESOURCES["concreteEnvironmentMetaModel"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_concrete_environment_meta_model(self, **params):
        return self._list("concreteEnvironmentMetaModel", **params)

    @http.route([RESOURCES["concreteEnvironmentMetaModel"]["path"], RESOURCES["concreteEnvironmentMetaModel"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_concrete_environment_meta_model(self, **_params):
        return self._create("concreteEnvironmentMetaModel")

    @http.route([f"{RESOURCES['concreteEnvironmentMetaModel']['path']}/<string:rid>", f"{RESOURCES['concreteEnvironmentMetaModel']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_concrete_environment_meta_model(self, rid, **params):
        return self._get("concreteEnvironmentMetaModel", rid, **params)

    @http.route([f"{RESOURCES['concreteEnvironmentMetaModel']['path']}/<string:rid>", f"{RESOURCES['concreteEnvironmentMetaModel']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_concrete_environment_meta_model(self, rid, **_params):
        return self._patch("concreteEnvironmentMetaModel", rid)

    @http.route([f"{RESOURCES['concreteEnvironmentMetaModel']['path']}/<string:rid>", f"{RESOURCES['concreteEnvironmentMetaModel']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_concrete_environment_meta_model(self, rid, **_params):
        return self._delete("concreteEnvironmentMetaModel", rid)

    @http.route([RESOURCES["testResourceAPI"]["path"], RESOURCES["testResourceAPI"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_resource_api(self, **params):
        return self._list("testResourceAPI", **params)

    @http.route([RESOURCES["testResourceAPI"]["path"], RESOURCES["testResourceAPI"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_resource_api(self, **_params):
        return self._create("testResourceAPI")

    @http.route([f"{RESOURCES['testResourceAPI']['path']}/<string:rid>", f"{RESOURCES['testResourceAPI']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_resource_api(self, rid, **params):
        return self._get("testResourceAPI", rid, **params)

    @http.route([f"{RESOURCES['testResourceAPI']['path']}/<string:rid>", f"{RESOURCES['testResourceAPI']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_resource_api(self, rid, **_params):
        return self._patch("testResourceAPI", rid)

    @http.route([f"{RESOURCES['testResourceAPI']['path']}/<string:rid>", f"{RESOURCES['testResourceAPI']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_resource_api(self, rid, **_params):
        return self._delete("testResourceAPI", rid)

    @http.route([RESOURCES["provisioningArtifact"]["path"], RESOURCES["provisioningArtifact"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_provisioning_artifact(self, **params):
        return self._list("provisioningArtifact", **params)

    @http.route([RESOURCES["provisioningArtifact"]["path"], RESOURCES["provisioningArtifact"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_provisioning_artifact(self, **_params):
        return self._create("provisioningArtifact")

    @http.route([f"{RESOURCES['provisioningArtifact']['path']}/<string:rid>", f"{RESOURCES['provisioningArtifact']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_provisioning_artifact(self, rid, **params):
        return self._get("provisioningArtifact", rid, **params)

    @http.route([f"{RESOURCES['provisioningArtifact']['path']}/<string:rid>", f"{RESOURCES['provisioningArtifact']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_provisioning_artifact(self, rid, **_params):
        return self._patch("provisioningArtifact", rid)

    @http.route([f"{RESOURCES['provisioningArtifact']['path']}/<string:rid>", f"{RESOURCES['provisioningArtifact']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_provisioning_artifact(self, rid, **_params):
        return self._delete("provisioningArtifact", rid)

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
                "name": f"tmf705-{api_name}-{callback}",
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

    @http.route(f"{API_BASE}/listener/abstractEnvironmentCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_ae_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/abstractEnvironmentChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_ae_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/abstractEnvironmentDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_ae_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/abstractEnvironmentAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_ae_attribute(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/abstractEnvironmentStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_ae_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/concreteEnvironmentMetaModelCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cemm_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/concreteEnvironmentMetaModelChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cemm_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/concreteEnvironmentMetaModelDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cemm_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/concreteEnvironmentMetaModelAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cemm_attribute(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/concreteEnvironmentMetaModelStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_cemm_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testResourceAPICreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tra_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testResourceAPIChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tra_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testResourceAPIDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tra_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testResourceAPIAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tra_attribute(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testResourceAPIStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tra_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/provisioningArtifactCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_pa_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/provisioningArtifactChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_pa_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/provisioningArtifactDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_pa_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/provisioningArtifactAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_pa_attribute(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/provisioningArtifactStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_pa_state(self, **_params):
        return self._listener_ok()
