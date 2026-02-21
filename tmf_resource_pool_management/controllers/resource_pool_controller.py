# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

from ..models.common import _filter_top_level_fields, _get_pagination, _json_dump


API_ROOT = "/tmf-api/resourcePoolManagement/v5"
CAP_SPEC = f"{API_ROOT}/capacitySpecification"
RP_SPEC = f"{API_ROOT}/resourcePoolSpecification"
RP = f"{API_ROOT}/resourcePool"


def _host():
    return request.httprequest.host_url.rstrip("/")


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        headers=[("Content-Type", "application/json")],
    )


def _body_json():
    raw = request.httprequest.data
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return json.loads(raw)


def _not_found():
    return _json_response({"error": "not found"}, status=404)


def _bad_request(msg="bad request", details=None):
    payload = {"error": msg}
    if details is not None:
        payload["details"] = details
    return _json_response(payload, status=400)


class TMF685Controller(http.Controller):

    # -------------------------
    # CapacitySpecification
    # -------------------------
    @http.route(CAP_SPEC, type="http", auth="public", methods=["GET"], csrf=False)
    def list_capacity_spec(self, **kwargs):
        fields_filter = kwargs.get("fields")
        offset, limit = _get_pagination(kwargs)

        recs = request.env["tmf.capacity.specification"].sudo().search([], offset=offset, limit=limit)
        data = [r.to_tmf_json(_host(), fields_filter=fields_filter) for r in recs]
        return _json_response(data)

    @http.route(CAP_SPEC + "/<string:cid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_capacity_spec(self, cid, **kwargs):
        fields_filter = kwargs.get("fields")
        rec = request.env["tmf.capacity.specification"].sudo().search([("tmf_id", "=", cid)], limit=1)
        if not rec:
            return _not_found()
        return _json_response(rec.to_tmf_json(_host(), fields_filter=fields_filter))

    @http.route(CAP_SPEC, type="http", auth="public", methods=["POST"], csrf=False)
    def create_capacity_spec(self, **kwargs):
        body = _body_json()

        # Conformance doc says POST /capacitySpecification mandatory @type only :contentReference[oaicite:3]{index=3}
        tmf_type = body.get("@type") or "CapacitySpecification"

        rec = request.env["tmf.capacity.specification"].sudo().create({
            "tmf_type": tmf_type,
            "capacity_characteristic_specification": _json_dump(body.get("capacityCharacteristicSpecification") or []),
            "external_identifier": _json_dump(body.get("externalIdentifier")),
            "related_capacity_specification": _json_dump(body.get("relatedCapacitySpecification") or []),
        })

        return _json_response(rec.to_tmf_json(_host()), status=201)

    # -------------------------
    # ResourcePoolSpecification
    # -------------------------
    @http.route(RP_SPEC, type="http", auth="public", methods=["GET"], csrf=False)
    def list_rp_spec(self, **kwargs):
        fields_filter = kwargs.get("fields")
        offset, limit = _get_pagination(kwargs)

        recs = request.env["tmf.resource.pool.specification"].sudo().search([], offset=offset, limit=limit)
        data = [r.to_tmf_json(_host(), fields_filter=fields_filter) for r in recs]
        return _json_response(data)

    @http.route(RP_SPEC + "/<string:sid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_rp_spec(self, sid, **kwargs):
        fields_filter = kwargs.get("fields")
        rec = request.env["tmf.resource.pool.specification"].sudo().search([("tmf_id", "=", sid)], limit=1)
        if not rec:
            return _not_found()
        return _json_response(rec.to_tmf_json(_host(), fields_filter=fields_filter))

    @http.route(RP_SPEC, type="http", auth="public", methods=["POST"], csrf=False)
    def create_rp_spec(self, **kwargs):
        body = _body_json()

        # Conformance: mandatory in POST: name, @type :contentReference[oaicite:4]{index=4}
        if not body.get("name"):
            return _bad_request("Missing mandatory attribute", details=["name"])

        tmf_type = body.get("@type") or "ResourcePoolSpecification"

        # Conformance says capacitySpecification is mandatory in response; keep required in storage too
        cap_spec = body.get("capacitySpecification")
        if not cap_spec:
            return _bad_request("Missing mandatory attribute", details=["capacitySpecification"])

        rec = request.env["tmf.resource.pool.specification"].sudo().create({
            "tmf_type": tmf_type,
            "name": body.get("name"),
            "description": body.get("description"),
            "capacity_specification": _json_dump(cap_spec),
            "attachment": _json_dump(body.get("attachment")),
            "external_identifier": _json_dump(body.get("externalIdentifier")),
            "feature_specification": _json_dump(body.get("featureSpecification")),
            "related_party": _json_dump(body.get("relatedParty")),
            "target_resource_schema": _json_dump(body.get("targetResourceSchema")),
        })

        return _json_response(rec.to_tmf_json(_host()), status=201)

    # -------------------------
    # ResourcePool
    # -------------------------
    @http.route(RP, type="http", auth="public", methods=["GET"], csrf=False)
    def list_resource_pool(self, **kwargs):
        fields_filter = kwargs.get("fields")
        offset, limit = _get_pagination(kwargs)

        recs = request.env["tmf.resource.pool"].sudo().search([], offset=offset, limit=limit)
        data = [r.to_tmf_json(_host(), fields_filter=fields_filter) for r in recs]
        return _json_response(data)

    @http.route(RP + "/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource_pool(self, rid, **kwargs):
        fields_filter = kwargs.get("fields")
        rec = request.env["tmf.resource.pool"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _not_found()
        return _json_response(rec.to_tmf_json(_host(), fields_filter=fields_filter))

    @http.route(RP, type="http", auth="public", methods=["POST"], csrf=False)
    def create_resource_pool(self, **kwargs):
        body = _body_json()

        # Conformance: mandatory in POST: capacity, name, pooledResource, pooledResourceSpecification, @type :contentReference[oaicite:5]{index=5}
        missing = []
        for k in ["capacity", "name", "pooledResource", "pooledResourceSpecification"]:
            if body.get(k) in (None, "", []):
                missing.append(k)
        if missing:
            return _bad_request("Missing mandatory attribute", details=missing)

        tmf_type = body.get("@type") or "ResourcePool"

        rec = request.env["tmf.resource.pool"].sudo().create({
            "tmf_type": tmf_type,
            "name": body.get("name"),
            "description": body.get("description"),

            "capacity": _json_dump(body.get("capacity")),
            "pooled_resource": _json_dump(body.get("pooledResource")),
            "pooled_resource_specification": _json_dump(body.get("pooledResourceSpecification")),

            "activation_feature": _json_dump(body.get("activationFeature")),
            "related_party": _json_dump(body.get("relatedParty")),
            "place": _json_dump(body.get("place")),
            "resource_characteristic": _json_dump(body.get("resourceCharacteristic")),
            "resource_relationship": _json_dump(body.get("resourceRelationship")),
            "supporting_resource": _json_dump(body.get("supportingResource")),
            "resource_specification": _json_dump(body.get("resourceSpecification")),

            "administrative_state": body.get("administrativeState"),
            "operational_state": body.get("operationalState"),
            "usage_state": body.get("usageState"),
            "resource_status": body.get("resourceStatus"),
        })

        return _json_response(rec.to_tmf_json(_host()), status=201)

    @http.route(RP + "/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_resource_pool(self, rid, **kwargs):
        body = _body_json()

        rec = request.env["tmf.resource.pool"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _not_found()

        # Conformance: JSON Merge Patch; non-patchable: href,id,@type,@baseType,@schemaLocation :contentReference[oaicite:6]{index=6}
        forbidden = {"id", "href", "@type", "@baseType", "@schemaLocation"}
        bad = [k for k in body.keys() if k in forbidden]
        if bad:
            return _bad_request("Non patchable attribute", details=bad)

        vals = {}
        # only update known fields
        mapping = {
            "name": "name",
            "description": "description",
            "capacity": "capacity",
            "pooledResource": "pooled_resource",
            "pooledResourceSpecification": "pooled_resource_specification",
            "activationFeature": "activation_feature",
            "relatedParty": "related_party",
            "place": "place",
            "resourceCharacteristic": "resource_characteristic",
            "resourceRelationship": "resource_relationship",
            "supportingResource": "supporting_resource",
            "resourceSpecification": "resource_specification",
            "administrativeState": "administrative_state",
            "operationalState": "operational_state",
            "usageState": "usage_state",
            "resourceStatus": "resource_status",
        }

        for k, field_name in mapping.items():
            if k in body:
                if field_name in {
                    "capacity",
                    "pooled_resource",
                    "pooled_resource_specification",
                    "activation_feature",
                    "related_party",
                    "place",
                    "resource_characteristic",
                    "resource_relationship",
                    "supporting_resource",
                    "resource_specification",
                }:
                    vals[field_name] = _json_dump(body.get(k))
                else:
                    vals[field_name] = body.get(k)

        if vals:
            rec.write(vals)

        return _json_response(rec.to_tmf_json(_host()), status=200)

    # -------------------------
    # Sub-resources: Push / Extract / AvailabilityCheck
    # -------------------------
    def _find_pool(self, resourcePoolId):
        return request.env["tmf.resource.pool"].sudo().search([("tmf_id", "=", resourcePoolId)], limit=1)

    # ---- Push
    @http.route(RP + "/<string:resourcePoolId>/push", type="http", auth="public", methods=["GET"], csrf=False)
    def list_push(self, resourcePoolId, **kwargs):
        fields_filter = kwargs.get("fields")
        offset, limit = _get_pagination(kwargs)

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        recs = request.env["tmf.resource.pool.push"].sudo().search(
            [("resource_pool_id", "=", pool.id)],
            offset=offset,
            limit=limit,
        )
        data = [r.to_tmf_json(_host(), fields_filter=fields_filter) for r in recs]
        return _json_response(data)

    @http.route(RP + "/<string:resourcePoolId>/push/<string:pid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_push(self, resourcePoolId, pid, **kwargs):
        fields_filter = kwargs.get("fields")

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        rec = request.env["tmf.resource.pool.push"].sudo().search(
            [("resource_pool_id", "=", pool.id), ("tmf_id", "=", pid)],
            limit=1,
        )
        if not rec:
            return _not_found()

        return _json_response(rec.to_tmf_json(_host(), fields_filter=fields_filter))

    @http.route(RP + "/<string:resourcePoolId>/push", type="http", auth="public", methods=["POST"], csrf=False)
    def create_push(self, resourcePoolId, **kwargs):
        body = _body_json()

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        # Keep input flexible, but ensure response mandatory fields exist
        tmf_type = body.get("@type") or "Push"
        pushed_resource = body.get("pushedResource") or []
        state = body.get("state") or "acknowledged"

        rec = request.env["tmf.resource.pool.push"].sudo().create({
            "tmf_type": tmf_type,
            "resource_pool_id": pool.id,
            "state": state,
            "error_message": _json_dump(body.get("errorMessage")),
            "pushed_resource": _json_dump(pushed_resource),
        })

        return _json_response(rec.to_tmf_json(_host()), status=201)

    # ---- Extract
    @http.route(RP + "/<string:resourcePoolId>/extract", type="http", auth="public", methods=["GET"], csrf=False)
    def list_extract(self, resourcePoolId, **kwargs):
        fields_filter = kwargs.get("fields")
        offset, limit = _get_pagination(kwargs)

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        recs = request.env["tmf.resource.pool.extract"].sudo().search(
            [("resource_pool_id", "=", pool.id)],
            offset=offset,
            limit=limit,
        )
        data = [r.to_tmf_json(_host(), fields_filter=fields_filter) for r in recs]
        return _json_response(data)

    @http.route(RP + "/<string:resourcePoolId>/extract/<string:eid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_extract(self, resourcePoolId, eid, **kwargs):
        fields_filter = kwargs.get("fields")

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        rec = request.env["tmf.resource.pool.extract"].sudo().search(
            [("resource_pool_id", "=", pool.id), ("tmf_id", "=", eid)],
            limit=1,
        )
        if not rec:
            return _not_found()

        return _json_response(rec.to_tmf_json(_host(), fields_filter=fields_filter))

    @http.route(RP + "/<string:resourcePoolId>/extract", type="http", auth="public", methods=["POST"], csrf=False)
    def create_extract(self, resourcePoolId, **kwargs):
        body = _body_json()

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        tmf_type = body.get("@type") or "Extract"
        state = body.get("state") or "acknowledged"

        # capacityDemand + extractedResource are mandatory in our storage to guarantee response
        if body.get("capacityDemand") is None:
            return _bad_request("Missing mandatory attribute", details=["capacityDemand"])
        if body.get("extractedResource") is None:
            return _bad_request("Missing mandatory attribute", details=["extractedResource"])

        rec = request.env["tmf.resource.pool.extract"].sudo().create({
            "tmf_type": tmf_type,
            "resource_pool_id": pool.id,
            "state": state,
            "capacity_demand": _json_dump(body.get("capacityDemand")),
            "error_message": _json_dump(body.get("errorMessage")),
            "extracted_resource": _json_dump(body.get("extractedResource")),
        })

        return _json_response(rec.to_tmf_json(_host()), status=201)

    # ---- AvailabilityCheck
    @http.route(RP + "/<string:resourcePoolId>/availabilityCheck", type="http", auth="public", methods=["GET"], csrf=False)
    def list_availability(self, resourcePoolId, **kwargs):
        fields_filter = kwargs.get("fields")
        offset, limit = _get_pagination(kwargs)

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        recs = request.env["tmf.resource.pool.availability.check"].sudo().search(
            [("resource_pool_id", "=", pool.id)],
            offset=offset,
            limit=limit,
        )
        data = [r.to_tmf_json(_host(), fields_filter=fields_filter) for r in recs]
        return _json_response(data)

    @http.route(RP + "/<string:resourcePoolId>/availabilityCheck/<string:aid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_availability(self, resourcePoolId, aid, **kwargs):
        fields_filter = kwargs.get("fields")

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        rec = request.env["tmf.resource.pool.availability.check"].sudo().search(
            [("resource_pool_id", "=", pool.id), ("tmf_id", "=", aid)],
            limit=1,
        )
        if not rec:
            return _not_found()

        return _json_response(rec.to_tmf_json(_host(), fields_filter=fields_filter))

    @http.route(RP + "/<string:resourcePoolId>/availabilityCheck", type="http", auth="public", methods=["POST"], csrf=False)
    def create_availability(self, resourcePoolId, **kwargs):
        body = _body_json()

        pool = self._find_pool(resourcePoolId)
        if not pool:
            return _not_found()

        tmf_type = body.get("@type") or "AvailabilityCheck"
        state = body.get("state") or "acknowledged"

        if body.get("capacityDemand") is None:
            return _bad_request("Missing mandatory attribute", details=["capacityDemand"])

        rec = request.env["tmf.resource.pool.availability.check"].sudo().create({
            "tmf_type": tmf_type,
            "resource_pool_id": pool.id,
            "state": state,
            "capacity_demand": _json_dump(body.get("capacityDemand")),
            "capacity_option": _json_dump(body.get("capacityOption")),
            "error_message": _json_dump(body.get("errorMessage")),
        })

        return _json_response(rec.to_tmf_json(_host()), status=201)
