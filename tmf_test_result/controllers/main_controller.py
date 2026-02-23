import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/testResult/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "testCaseResult": {
        "model": "tmf.test.case.result",
        "path": f"{API_BASE}/testCaseResult",
        "alt_path": f"{API_BASE}/TestCaseResult",
        "required": ["testCaseResultDefinition", "testExecution"],
    },
    "testSuiteResult": {
        "model": "tmf.test.suite.result",
        "path": f"{API_BASE}/testSuiteResult",
        "alt_path": f"{API_BASE}/TestSuiteResult",
        "required": ["testSuiteResultDefinition", "testExecution"],
    },
    "nonFunctionalTestResult": {
        "model": "tmf.non.functional.test.result",
        "path": f"{API_BASE}/nonFunctionalTestResult",
        "alt_path": f"{API_BASE}/NonFunctionalTestResult",
        "required": ["nonFunctionalTestResultDefinition", "testExecution"],
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
    if "nonfunctionaltestresult" in q:
        return "nonFunctionalTestResult"
    if "testsuiteresult" in q:
        return "testSuiteResult"
    return "testCaseResult"


class TMF707Controller(http.Controller):
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

    @http.route([RESOURCES["testCaseResult"]["path"], RESOURCES["testCaseResult"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_case_result(self, **params):
        return self._list("testCaseResult", **params)

    @http.route([RESOURCES["testCaseResult"]["path"], RESOURCES["testCaseResult"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_case_result(self, **_params):
        return self._create("testCaseResult")

    @http.route([f"{RESOURCES['testCaseResult']['path']}/<string:rid>", f"{RESOURCES['testCaseResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_case_result(self, rid, **params):
        return self._get("testCaseResult", rid, **params)

    @http.route([f"{RESOURCES['testCaseResult']['path']}/<string:rid>", f"{RESOURCES['testCaseResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_case_result(self, rid, **_params):
        return self._patch("testCaseResult", rid)

    @http.route([f"{RESOURCES['testCaseResult']['path']}/<string:rid>", f"{RESOURCES['testCaseResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_case_result(self, rid, **_params):
        return self._delete("testCaseResult", rid)

    @http.route([RESOURCES["testSuiteResult"]["path"], RESOURCES["testSuiteResult"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_test_suite_result(self, **params):
        return self._list("testSuiteResult", **params)

    @http.route([RESOURCES["testSuiteResult"]["path"], RESOURCES["testSuiteResult"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_test_suite_result(self, **_params):
        return self._create("testSuiteResult")

    @http.route([f"{RESOURCES['testSuiteResult']['path']}/<string:rid>", f"{RESOURCES['testSuiteResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_test_suite_result(self, rid, **params):
        return self._get("testSuiteResult", rid, **params)

    @http.route([f"{RESOURCES['testSuiteResult']['path']}/<string:rid>", f"{RESOURCES['testSuiteResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_test_suite_result(self, rid, **_params):
        return self._patch("testSuiteResult", rid)

    @http.route([f"{RESOURCES['testSuiteResult']['path']}/<string:rid>", f"{RESOURCES['testSuiteResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_test_suite_result(self, rid, **_params):
        return self._delete("testSuiteResult", rid)

    @http.route([RESOURCES["nonFunctionalTestResult"]["path"], RESOURCES["nonFunctionalTestResult"]["alt_path"]], type="http", auth="public", methods=["GET"], csrf=False)
    def list_non_functional_test_result(self, **params):
        return self._list("nonFunctionalTestResult", **params)

    @http.route([RESOURCES["nonFunctionalTestResult"]["path"], RESOURCES["nonFunctionalTestResult"]["alt_path"]], type="http", auth="public", methods=["POST"], csrf=False)
    def create_non_functional_test_result(self, **_params):
        return self._create("nonFunctionalTestResult")

    @http.route([f"{RESOURCES['nonFunctionalTestResult']['path']}/<string:rid>", f"{RESOURCES['nonFunctionalTestResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["GET"], csrf=False)
    def get_non_functional_test_result(self, rid, **params):
        return self._get("nonFunctionalTestResult", rid, **params)

    @http.route([f"{RESOURCES['nonFunctionalTestResult']['path']}/<string:rid>", f"{RESOURCES['nonFunctionalTestResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_non_functional_test_result(self, rid, **_params):
        return self._patch("nonFunctionalTestResult", rid)

    @http.route([f"{RESOURCES['nonFunctionalTestResult']['path']}/<string:rid>", f"{RESOURCES['nonFunctionalTestResult']['alt_path']}/<string:rid>"], type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_non_functional_test_result(self, rid, **_params):
        return self._delete("nonFunctionalTestResult", rid)

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
                "name": f"tmf707-{api_name}-{callback}",
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

    @http.route(f"{API_BASE}/listener/testCaseResultCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_test_case_result_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testCaseResultChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_test_case_result_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testCaseResultDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_test_case_result_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteResultCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_test_suite_result_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteResultChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_test_suite_result_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/testSuiteResultDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_test_suite_result_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestResultCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_non_functional_test_result_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestResultChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_non_functional_test_result_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/nonFunctionalTestResultDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_non_functional_test_result_delete(self, **_params):
        return self._listener_ok()
