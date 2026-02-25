import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/metadataCatalog/v4"
NON_PATCHABLE = {"id", "href"}

RESOURCES = {
    "metadataCatalog": {
        "model": "tmf.metadata.catalog",
        "path": f"{API_BASE}/metadataCatalog",
        "required": ["name", "description"],
    },
    "metadataCategory": {
        "model": "tmf.metadata.category",
        "path": f"{API_BASE}/metadataCategory",
        "required": ["name", "description"],
    },
    "metadataCatalogItem": {
        "model": "tmf.metadata.catalog.item",
        "path": f"{API_BASE}/metadataCatalogItem",
        "required": ["name", "description", "specification"],
    },
    "metadataSpecification": {
        "model": "tmf.metadata.specification",
        "path": f"{API_BASE}/metadataSpecification",
        "required": ["name", "description", "@type"],
    },
}

FILTER_MAP = {
    "metadataCatalog": {"id": "tmf_id", "name": "name"},
    "metadataCategory": {"id": "tmf_id", "name": "name", "lifecycleStatus": "lifecycle_status"},
    "metadataCatalogItem": {"id": "tmf_id", "name": "name", "lifecycleStatus": "lifecycle_status"},
    "metadataSpecification": {"id": "tmf_id", "name": "name", "lifecycleStatus": "lifecycle_status"},
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
    if "metadataspecification" in q:
        return "metadataSpecification"
    if "metadatacatalogitem" in q:
        return "metadataCatalogItem"
    if "metadatacategory" in q:
        return "metadataCategory"
    return "metadataCatalog"


class TMF725Controller(http.Controller):
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

    @http.route(RESOURCES["metadataCatalog"]["path"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_metadata_catalog(self, **params):
        return self._list("metadataCatalog", **params)

    @http.route(RESOURCES["metadataCatalog"]["path"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_metadata_catalog(self, **_params):
        return self._create("metadataCatalog")

    @http.route(f"{RESOURCES['metadataCatalog']['path']}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_metadata_catalog(self, rid, **params):
        return self._get("metadataCatalog", rid, **params)

    @http.route(f"{RESOURCES['metadataCatalog']['path']}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_metadata_catalog(self, rid, **_params):
        return self._patch("metadataCatalog", rid)

    @http.route(f"{RESOURCES['metadataCatalog']['path']}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_metadata_catalog(self, rid, **_params):
        return self._delete("metadataCatalog", rid)

    @http.route(RESOURCES["metadataCategory"]["path"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_metadata_category(self, **params):
        return self._list("metadataCategory", **params)

    @http.route(RESOURCES["metadataCategory"]["path"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_metadata_category(self, **_params):
        return self._create("metadataCategory")

    @http.route(f"{RESOURCES['metadataCategory']['path']}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_metadata_category(self, rid, **params):
        return self._get("metadataCategory", rid, **params)

    @http.route(f"{RESOURCES['metadataCategory']['path']}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_metadata_category(self, rid, **_params):
        return self._patch("metadataCategory", rid)

    @http.route(f"{RESOURCES['metadataCategory']['path']}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_metadata_category(self, rid, **_params):
        return self._delete("metadataCategory", rid)

    @http.route(RESOURCES["metadataCatalogItem"]["path"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_metadata_catalog_item(self, **params):
        return self._list("metadataCatalogItem", **params)

    @http.route(RESOURCES["metadataCatalogItem"]["path"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_metadata_catalog_item(self, **_params):
        return self._create("metadataCatalogItem")

    @http.route(f"{RESOURCES['metadataCatalogItem']['path']}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_metadata_catalog_item(self, rid, **params):
        return self._get("metadataCatalogItem", rid, **params)

    @http.route(f"{RESOURCES['metadataCatalogItem']['path']}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_metadata_catalog_item(self, rid, **_params):
        return self._patch("metadataCatalogItem", rid)

    @http.route(f"{RESOURCES['metadataCatalogItem']['path']}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_metadata_catalog_item(self, rid, **_params):
        return self._delete("metadataCatalogItem", rid)

    @http.route(RESOURCES["metadataSpecification"]["path"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_metadata_specification(self, **params):
        return self._list("metadataSpecification", **params)

    @http.route(RESOURCES["metadataSpecification"]["path"], type="http", auth="public", methods=["POST"], csrf=False)
    def create_metadata_specification(self, **_params):
        return self._create("metadataSpecification")

    @http.route(f"{RESOURCES['metadataSpecification']['path']}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_metadata_specification(self, rid, **params):
        return self._get("metadataSpecification", rid, **params)

    @http.route(f"{RESOURCES['metadataSpecification']['path']}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_metadata_specification(self, rid, **_params):
        return self._patch("metadataSpecification", rid)

    @http.route(f"{RESOURCES['metadataSpecification']['path']}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_metadata_specification(self, rid, **_params):
        return self._delete("metadataSpecification", rid)

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
                "name": f"tmf725-{api_name}-{callback}",
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

    @http.route(f"{API_BASE}/listener/metadataCatalogCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCategoryCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_category_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCategoryAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_category_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCategoryStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_category_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCategoryDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_category_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogItemCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_item_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogItemAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_item_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogItemStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_item_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataCatalogItemDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_catalog_item_delete(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_specification_create(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_specification_change(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataSpecificationStatusChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_specification_status(self, **_params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/metadataSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_metadata_specification_delete(self, **_params):
        return self._listener_ok()

