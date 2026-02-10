# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


API_BASE = "/tmf-api/serviceQualificationManagement/v4"


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _error(status, reason, code=None, details=None):
    payload = {"error": {"status": status, "reason": reason}}
    if code:
        payload["error"]["code"] = code
    if details is not None:
        payload["error"]["details"] = details
    return _json_response(payload, status=status)


def _parse_json_body():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _apply_fields(obj: dict, fields_param):
    # Spec: attribute selection enabled for first-level attributes
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in wanted}


def _domain_from_params(params):
    domain = []
    if "state" in params:
        domain.append(("state", "=", params.get("state")))
    if "externalId" in params:
        domain.append(("external_id", "=", params.get("externalId")))
    return domain


def _ensure_items_for_check(payload):
    # Mandatory: serviceQualificationItem (for Check)
    items = payload.get("serviceQualificationItem")
    if not isinstance(items, list) or not items:
        return None, _error(400, "Missing mandatory attribute serviceQualificationItem", code="invalidBody")
    return items, None


class TMF645QualificationController(http.Controller):

    # -------------------------
    # CHECK: list / get / post / patch / delete
    # -------------------------
    @http.route(f"{API_BASE}/checkServiceQualification", type="http", auth="public", methods=["GET"], csrf=False)
    def list_check(self, **params):
        domain = _domain_from_params(params)
        domain.append(("qualification_kind", "=", "check"))

        records = request.env["tmf.service.qualification"].sudo().search(domain)
        fields_param = params.get("fields")
        data = [_apply_fields(r.to_tmf_json(), fields_param) for r in records]
        return _json_response(data, status=200)

    @http.route(f"{API_BASE}/checkServiceQualification/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_check(self, rid, **params):
        rec = request.env["tmf.service.qualification"].sudo().search(
            [("tmf_id", "=", rid), ("qualification_kind", "=", "check")], limit=1
        )
        if not rec:
            return _error(404, "Not found", code="notFound")

        return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/checkServiceQualification", type="http", auth="public", methods=["POST"], csrf=False)
    def create_check(self, **params):
        payload = _parse_json_body()
        if payload is None:
            return _error(400, "Invalid JSON body", code="invalidBody")

        items, err = _ensure_items_for_check(payload)
        if err:
            return err

        vals = {
            "qualification_kind": "check",
            "description": payload.get("description"),
            "external_id": payload.get("externalId"),
            "instant_sync_qualification": bool(payload.get("instantSyncQualification", False)),
            "provide_alternative": bool(payload.get("provideAlternative", False)),
            "provide_unavailability_reason": bool(payload.get("provideUnavailabilityReason", False)),
            "related_party_json": json.dumps(payload.get("relatedParty") or [], ensure_ascii=False),
            "expected_qualification_date": payload.get("expectedQualificationDate"),
            "estimated_response_date": payload.get("estimatedResponseDate"),
            "expiration_date": payload.get("expirationDate"),
            "service_qualification_item_json": json.dumps(items, ensure_ascii=False),
        }

        # Optional convenience mapping from first item.service
        first = items[0] if items else {}
        svc = first.get("service") or {}
        place_arr = svc.get("place") or []
        if isinstance(place_arr, list) and place_arr:
            place_id_tmf = (place_arr[0] or {}).get("id")
            if place_id_tmf:
                addr = request.env["tmf.geographic.address"].sudo().search([("tmf_id", "=", place_id_tmf)], limit=1)
                if addr:
                    vals["place_id"] = addr.id

        spec = (svc.get("serviceSpecification") or {})
        spec_id_tmf = spec.get("id")
        if spec_id_tmf:
            sp = request.env["tmf.product.specification"].sudo().search([("tmf_id", "=", spec_id_tmf)], limit=1)
            if sp:
                vals["service_specification_id"] = sp.id

        rec = request.env["tmf.service.qualification"].sudo().create(vals)

        # Spec: instantSyncQualification=true => 200, else 201 :contentReference[oaicite:5]{index=5}
        status = 200 if rec.instant_sync_qualification else 201
        return _json_response(rec.to_tmf_json(), status=status)

    @http.route(f"{API_BASE}/checkServiceQualification/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_check(self, rid, **params):
        rec = request.env["tmf.service.qualification"].sudo().search(
            [("tmf_id", "=", rid), ("qualification_kind", "=", "check")], limit=1
        )
        if not rec:
            return _error(404, "Not found", code="notFound")

        # Spec: support json/merge is mandatory :contentReference[oaicite:6]{index=6}
        patch = _parse_json_body()
        if patch is None:
            return _error(400, "Invalid JSON body", code="invalidBody")

        # Non patchable: id, href, checkServiceQualificationDate :contentReference[oaicite:7]{index=7}
        for forbidden in ("id", "href", "checkServiceQualificationDate"):
            if forbidden in patch:
                return _error(400, f"Non patchable attribute: {forbidden}", code="invalidPatch")

        write_vals = {}

        if "description" in patch:
            write_vals["description"] = patch.get("description")
        if "externalId" in patch:
            write_vals["external_id"] = patch.get("externalId")
        if "expectedQualificationDate" in patch:
            write_vals["expected_qualification_date"] = patch.get("expectedQualificationDate")
        if "estimatedResponseDate" in patch:
            write_vals["estimated_response_date"] = patch.get("estimatedResponseDate")
        if "expirationDate" in patch:
            write_vals["expiration_date"] = patch.get("expirationDate")
        if "instantSyncQualification" in patch:
            write_vals["instant_sync_qualification"] = bool(patch.get("instantSyncQualification"))
        if "provideAlternative" in patch:
            write_vals["provide_alternative"] = bool(patch.get("provideAlternative"))
        if "provideUnavailabilityReason" in patch:
            write_vals["provide_unavailability_reason"] = bool(patch.get("provideUnavailabilityReason"))
        if "qualificationResult" in patch:
            write_vals["qualification_result"] = patch.get("qualificationResult")
        if "state" in patch:
            write_vals["state"] = patch.get("state")
        if "relatedParty" in patch:
            write_vals["related_party_json"] = json.dumps(patch.get("relatedParty") or [], ensure_ascii=False)
        if "serviceQualificationItem" in patch:
            items = patch.get("serviceQualificationItem")
            if not isinstance(items, list) or not items:
                return _error(400, "serviceQualificationItem must be a non-empty array", code="invalidPatch")
            write_vals["service_qualification_item_json"] = json.dumps(items, ensure_ascii=False)

        if write_vals:
            rec.sudo().write(write_vals)

        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/checkServiceQualification/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_check(self, rid, **params):
        rec = request.env["tmf.service.qualification"].sudo().search(
            [("tmf_id", "=", rid), ("qualification_kind", "=", "check")], limit=1
        )
        if not rec:
            return _error(404, "Not found", code="notFound")
        rec.unlink()
        return request.make_response("", status=204)

    # -------------------------
    # QUERY: list / get / post / patch / delete (minimal scaffold)
    # -------------------------
    @http.route(f"{API_BASE}/queryServiceQualification", type="http", auth="public", methods=["GET"], csrf=False)
    def list_query(self, **params):
        domain = _domain_from_params(params)
        domain.append(("qualification_kind", "=", "query"))
        records = request.env["tmf.service.qualification"].sudo().search(domain)
        fields_param = params.get("fields")
        data = [_apply_fields(r.to_tmf_json(), fields_param) for r in records]
        return _json_response(data, status=200)

    @http.route(f"{API_BASE}/queryServiceQualification/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_query(self, rid, **params):
        rec = request.env["tmf.service.qualification"].sudo().search(
            [("tmf_id", "=", rid), ("qualification_kind", "=", "query")], limit=1
        )
        if not rec:
            return _error(404, "Not found", code="notFound")
        return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/queryServiceQualification", type="http", auth="public", methods=["POST"], csrf=False)
    def create_query(self, **params):
        payload = _parse_json_body()
        if payload is None:
            return _error(400, "Invalid JSON body", code="invalidBody")

        vals = {
            "qualification_kind": "query",
            "description": payload.get("description"),
            "external_id": payload.get("externalId"),
            "instant_sync_qualification": bool(payload.get("instantSyncQualification", False)),
            "related_party_json": json.dumps(payload.get("relatedParty") or [], ensure_ascii=False),
            "expected_qualification_date": payload.get("expectedQualificationDate"),
            "estimated_response_date": payload.get("estimatedResponseDate"),
            "expiration_date": payload.get("expirationDate"),
            "search_criteria_json": json.dumps(payload.get("searchCriteria") or {}, ensure_ascii=False),
            "service_qualification_item_json": json.dumps(payload.get("serviceQualificationItem") or [], ensure_ascii=False),
        }

        rec = request.env["tmf.service.qualification"].sudo().create(vals)
        status = 200 if rec.instant_sync_qualification else 201
        return _json_response(rec.to_tmf_json(), status=status)

    @http.route(f"{API_BASE}/queryServiceQualification/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_query(self, rid, **params):
        rec = request.env["tmf.service.qualification"].sudo().search(
            [("tmf_id", "=", rid), ("qualification_kind", "=", "query")], limit=1
        )
        if not rec:
            return _error(404, "Not found", code="notFound")

        patch = _parse_json_body()
        if patch is None:
            return _error(400, "Invalid JSON body", code="invalidBody")

        # For Query resource, enforce at least id/href/date immutability similarly (safe, consistent)
        for forbidden in ("id", "href", "queryServiceQualificationDate"):
            if forbidden in patch:
                return _error(400, f"Non patchable attribute: {forbidden}", code="invalidPatch")

        write_vals = {}
        if "description" in patch:
            write_vals["description"] = patch.get("description")
        if "externalId" in patch:
            write_vals["external_id"] = patch.get("externalId")
        if "expectedQualificationDate" in patch:
            write_vals["expected_qualification_date"] = patch.get("expectedQualificationDate")
        if "estimatedResponseDate" in patch:
            write_vals["estimated_response_date"] = patch.get("estimatedResponseDate")
        if "expirationDate" in patch:
            write_vals["expiration_date"] = patch.get("expirationDate")
        if "instantSyncQualification" in patch:
            write_vals["instant_sync_qualification"] = bool(patch.get("instantSyncQualification"))
        if "state" in patch:
            write_vals["state"] = patch.get("state")
        if "relatedParty" in patch:
            write_vals["related_party_json"] = json.dumps(patch.get("relatedParty") or [], ensure_ascii=False)
        if "searchCriteria" in patch:
            write_vals["search_criteria_json"] = json.dumps(patch.get("searchCriteria") or {}, ensure_ascii=False)
        if "serviceQualificationItem" in patch:
            write_vals["service_qualification_item_json"] = json.dumps(patch.get("serviceQualificationItem") or [], ensure_ascii=False)

        if write_vals:
            rec.sudo().write(write_vals)

        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/queryServiceQualification/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_query(self, rid, **params):
        rec = request.env["tmf.service.qualification"].sudo().search(
            [("tmf_id", "=", rid), ("qualification_kind", "=", "query")], limit=1
        )
        if not rec:
            return _error(404, "Not found", code="notFound")
        rec.unlink()
        return request.make_response("", status=204)
