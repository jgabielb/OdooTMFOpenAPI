import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/testExecution/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "testEnvironmentProvisioningExecution": {
        "model": "tmf.test.environment.provisioning.execution",
        "path": f"{API_BASE}/testEnvironmentProvisioningExecution",
        "alt_path": f"{API_BASE}/TestEnvironmentProvisioningExecution",
        "required": ["dataCorrelationId", "testEnvironmentAllocationExecution"],
    },
    "testEnvironmentAllocationExecution": {
        "model": "tmf.test.environment.allocation.execution",
        "path": f"{API_BASE}/testEnvironmentAllocationExecution",
        "alt_path": f"{API_BASE}/TestEnvironmentAllocationExecution",
        "required": ["abstractEnvironment", "dataCorrelationId", "resourceManagerUrl"],
    },
    "testSuiteExecution": {
        "model": "tmf.test.suite.execution",
        "path": f"{API_BASE}/testSuiteExecution",
        "alt_path": f"{API_BASE}/TestSuiteExecution",
        "required": ["testEnvironmentProvisioningExecution"],
    },
    "testCaseExecution": {
        "model": "tmf.test.case.execution",
        "path": f"{API_BASE}/testCaseExecution",
        "alt_path": f"{API_BASE}/TestCaseExecution",
        "required": ["testEnvironmentProvisioningExecution"],
    },
    "nonFunctionalTestExecution": {
        "model": "tmf.non.functional.test.execution",
        "path": f"{API_BASE}/nonFunctionalTestExecution",
        "alt_path": f"{API_BASE}/NonFunctionalTestExecution",
        "required": ["testEnvironmentProvisioningExecution"],
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
    if "testenvironmentallocationexecution" in q:
        return "testEnvironmentAllocationExecution"
    if "testsuiteexecution" in q:
        return "testSuiteExecution"
    if "testcaseexecution" in q:
        return "testCaseExecution"
    if "nonfunctionaltestexecution" in q:
        return "nonFunctionalTestExecution"
    return "testEnvironmentProvisioningExecution"


class TMF708Controller(http.Controller):
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

    @http.route([RESOURCES["testEnvironmentProvisioningExecution"]["path"], RESOURCES["testEnvironmentProvisioningExecution"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_environment_provisioning_execution(self, **params):
        return self._list("testEnvironmentProvisioningExecution", **params)

    @http.route([RESOURCES["testEnvironmentProvisioningExecution"]["path"], RESOURCES["testEnvironmentProvisioningExecution"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_environment_provisioning_execution(self, **_params):
        return self._create("testEnvironmentProvisioningExecution")

    @http.route([f"{RESOURCES['testEnvironmentProvisioningExecution']['path']}/<string:rid>", f"{RESOURCES['testEnvironmentProvisioningExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_environment_provisioning_execution(self, rid, **params):
        return self._get("testEnvironmentProvisioningExecution", rid, **params)

    @http.route([f"{RESOURCES['testEnvironmentProvisioningExecution']['path']}/<string:rid>", f"{RESOURCES['testEnvironmentProvisioningExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_environment_provisioning_execution(self, rid, **_params):
        return self._patch("testEnvironmentProvisioningExecution", rid)

    @http.route([f"{RESOURCES['testEnvironmentProvisioningExecution']['path']}/<string:rid>", f"{RESOURCES['testEnvironmentProvisioningExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_environment_provisioning_execution(self, rid, **_params):
        return self._delete("testEnvironmentProvisioningExecution", rid)

    @http.route([RESOURCES["testEnvironmentAllocationExecution"]["path"], RESOURCES["testEnvironmentAllocationExecution"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_environment_allocation_execution(self, **params):
        return self._list("testEnvironmentAllocationExecution", **params)

    @http.route([RESOURCES["testEnvironmentAllocationExecution"]["path"], RESOURCES["testEnvironmentAllocationExecution"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_environment_allocation_execution(self, **_params):
        return self._create("testEnvironmentAllocationExecution")

    @http.route([f"{RESOURCES['testEnvironmentAllocationExecution']['path']}/<string:rid>", f"{RESOURCES['testEnvironmentAllocationExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_environment_allocation_execution(self, rid, **params):
        return self._get("testEnvironmentAllocationExecution", rid, **params)

    @http.route([f"{RESOURCES['testEnvironmentAllocationExecution']['path']}/<string:rid>", f"{RESOURCES['testEnvironmentAllocationExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_environment_allocation_execution(self, rid, **_params):
        return self._patch("testEnvironmentAllocationExecution", rid)

    @http.route([f"{RESOURCES['testEnvironmentAllocationExecution']['path']}/<string:rid>", f"{RESOURCES['testEnvironmentAllocationExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_environment_allocation_execution(self, rid, **_params):
        return self._delete("testEnvironmentAllocationExecution", rid)

    @http.route([RESOURCES["testSuiteExecution"]["path"], RESOURCES["testSuiteExecution"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_suite_execution(self, **params):
        return self._list("testSuiteExecution", **params)

    @http.route([RESOURCES["testSuiteExecution"]["path"], RESOURCES["testSuiteExecution"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_suite_execution(self, **_params):
        return self._create("testSuiteExecution")

    @http.route([f"{RESOURCES['testSuiteExecution']['path']}/<string:rid>", f"{RESOURCES['testSuiteExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_suite_execution(self, rid, **params):
        return self._get("testSuiteExecution", rid, **params)

    @http.route([f"{RESOURCES['testSuiteExecution']['path']}/<string:rid>", f"{RESOURCES['testSuiteExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_suite_execution(self, rid, **_params):
        return self._patch("testSuiteExecution", rid)

    @http.route([f"{RESOURCES['testSuiteExecution']['path']}/<string:rid>", f"{RESOURCES['testSuiteExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_suite_execution(self, rid, **_params):
        return self._delete("testSuiteExecution", rid)

    @http.route([RESOURCES["testCaseExecution"]["path"], RESOURCES["testCaseExecution"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_case_execution(self, **params):
        return self._list("testCaseExecution", **params)

    @http.route([RESOURCES["testCaseExecution"]["path"], RESOURCES["testCaseExecution"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_case_execution(self, **_params):
        return self._create("testCaseExecution")

    @http.route([f"{RESOURCES['testCaseExecution']['path']}/<string:rid>", f"{RESOURCES['testCaseExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_case_execution(self, rid, **params):
        return self._get("testCaseExecution", rid, **params)

    @http.route([f"{RESOURCES['testCaseExecution']['path']}/<string:rid>", f"{RESOURCES['testCaseExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_case_execution(self, rid, **_params):
        return self._patch("testCaseExecution", rid)

    @http.route([f"{RESOURCES['testCaseExecution']['path']}/<string:rid>", f"{RESOURCES['testCaseExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_case_execution(self, rid, **_params):
        return self._delete("testCaseExecution", rid)

    @http.route([RESOURCES["nonFunctionalTestExecution"]["path"], RESOURCES["nonFunctionalTestExecution"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_non_functional_test_execution(self, **params):
        return self._list("nonFunctionalTestExecution", **params)

    @http.route([RESOURCES["nonFunctionalTestExecution"]["path"], RESOURCES["nonFunctionalTestExecution"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_non_functional_test_execution(self, **_params):
        return self._create("nonFunctionalTestExecution")

    @http.route([f"{RESOURCES['nonFunctionalTestExecution']['path']}/<string:rid>", f"{RESOURCES['nonFunctionalTestExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_non_functional_test_execution(self, rid, **params):
        return self._get("nonFunctionalTestExecution", rid, **params)

    @http.route([f"{RESOURCES['nonFunctionalTestExecution']['path']}/<string:rid>", f"{RESOURCES['nonFunctionalTestExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_non_functional_test_execution(self, rid, **_params):
        return self._patch("nonFunctionalTestExecution", rid)

    @http.route([f"{RESOURCES['nonFunctionalTestExecution']['path']}/<string:rid>", f"{RESOURCES['nonFunctionalTestExecution']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_non_functional_test_execution(self, rid, **_params):
        return self._delete("nonFunctionalTestExecution", rid)

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
                "name": f"tmf708-{api_name}-{callback}",
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

    @http.route(f"{API_BASE}/listener/testEnvironmentProvisioningExecutionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tepe_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentProvisioningExecutionChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tepe_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentProvisioningExecutionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tepe_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentProvisioningExecutionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tepe_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentAllocationExecutionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_teae_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentAllocationExecutionChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_teae_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentAllocationExecutionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_teae_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testEnvironmentAllocationExecutionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_teae_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteExecutionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tse_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteExecutionChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tse_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteExecutionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tse_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteExecutionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tse_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testCaseExecutionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tce_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testCaseExecutionChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tce_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testCaseExecutionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tce_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testCaseExecutionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_tce_state(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestExecutionCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_nfte_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestExecutionChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_nfte_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestExecutionDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_nfte_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestExecutionStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_nfte_state(self, **_params):
        return self._listener_ok()
