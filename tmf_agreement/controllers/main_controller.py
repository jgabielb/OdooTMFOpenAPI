# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
from datetime import datetime, timezone

API_BASE = "/tmf-api/agreementManagement/v4"

# --------
# Helpers
# --------
def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)

def _error(status, reason, code=None, details=None):
    payload = {"error": {"status": status, "reason": reason}}
    if code:
        payload["error"]["code"] = code
    if details:
        payload["error"]["details"] = details
    return _json_response(payload, status=status)

def _parse_json_body():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None

def _fields_param_to_odoo(fields_param):
    """
    TMF 'fields' query is attribute selection.
    Minimal implementation: ignore server-side projection and return full resource.
    (You can implement projection later if needed.)
    """
    return None

def _require_fields(data: dict, required: list):
    missing = [k for k in required if k not in data or data[k] in (None, "", [], {})]
    return missing

# TMF -> Odoo mapping for Agreement
AGREEMENT_TMF_TO_ODOO = {
    "agreementType": "agreement_type",
    "description": "description",
    "documentNumber": "document_number",
    "initialDate": "initial_date",
    "name": "name",
    "statementOfIntent": "statement_of_intent",
    "status": "status",
    "version": "version",
    "agreementAuthorization": "agreement_authorization",
    "agreementItem": "agreement_item",
    "agreementPeriod": "agreement_period",
    "agreementSpecification": "agreement_specification",
    "associatedAgreement": "associated_agreement",
    "characteristic": "characteristic",
    "completionDate": "completion_date",
    "engagedParty": "engaged_party",
}

# TMF -> Odoo mapping for AgreementSpecification (you must add the model fields, see next section)
AGRSPEC_TMF_TO_ODOO = {
    "name": "name",
    "description": "description",
    "isBundle": "is_bundle",
    "lastUpdate": "last_update",
    "lifecycleStatus": "lifecycle_status",
    "relatedParty": "related_party",
    "serviceCategory": "service_category",
    "specificationCharacteristic": "specification_characteristic",
    "specificationRelationship": "specification_relationship",
    "validFor": "valid_for",
    "version": "version",
    "attachment": "attachment",
}

class TMF651Controller(http.Controller):
    def _listener_ok(self):
        data = _parse_json_body()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON")
        return request.make_response("", status=201)

    # --------------------------
    # Agreement (TMF651)
    # --------------------------
    @http.route(f"{API_BASE}/agreement", type="http", auth="public", methods=["GET"], csrf=False)
    def list_agreement(self, **params):
        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        env = request.env["tmf.agreement"].sudo()
        recs = env.search([], limit=limit, offset=offset, order="id asc")
        total = env.search_count([])
        payload = [r.to_tmf_json() for r in recs]
        return _json_response(payload, status=200, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(payload))),
        ])

    @http.route(f"{API_BASE}/agreement/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def retrieve_agreement(self, tmf_id, **params):
        rec = request.env["tmf.agreement"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not found")
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/agreement", type="http", auth="public", methods=["POST"], csrf=False)
    def create_agreement(self, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON")

        # Mandatory attributes per spec: agreementItem, engagedParty, name, agreementType
        # Additional rule: engagedParty.name mandatory
        missing = _require_fields(data, ["agreementItem", "engagedParty", "name", "agreementType"])
        if missing:
            return _error(400, "Missing mandatory attributes", details={"missing": missing})

        engaged_party = data.get("engagedParty")
        # spec says engagedParty is list [1..*]; enforce minimally
        if not isinstance(engaged_party, list) or len(engaged_party) == 0 or not engaged_party[0].get("name"):
            return _error(400, "Missing mandatory sub-attribute engagedParty.name")

        vals = {}
        for tmf_key, odoo_field in AGREEMENT_TMF_TO_ODOO.items():
            if tmf_key in data:
                vals[odoo_field] = data[tmf_key]

        # Default values per spec
        # completionDate default = current date; version default = "0"
        if not vals.get("completion_date"):
            vals["completion_date"] = datetime.now(timezone.utc).isoformat()
        if not vals.get("version"):
            vals["version"] = "0"

        rec = request.env["tmf.agreement"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/agreement/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_agreement(self, tmf_id, **params):
        # TMF651: JSON Merge Patch support is mandatory :contentReference[oaicite:4]{index=4}
        content_type = (request.httprequest.content_type or "").lower()
        if "merge-patch" not in content_type and "application/json" not in content_type:
            # be strict if you want: require application/merge-patch+json
            pass

        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON")

        rec = request.env["tmf.agreement"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not found")

        # Non-patchable: completionDate, href, id 
        for forbidden in ("id", "href", "completionDate"):
            if forbidden in data:
                return _error(400, f"Non patchable attribute: {forbidden}")

        vals = {}
        for tmf_key, odoo_field in AGREEMENT_TMF_TO_ODOO.items():
            if tmf_key in data:
                vals[odoo_field] = data[tmf_key]

        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/agreement/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_agreement(self, tmf_id, **params):
        rec = request.env["tmf.agreement"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not found")
        rec.unlink()
        return request.make_response("", status=204)

    # --------------------------
    # AgreementSpecification
    # --------------------------
    @http.route(f"{API_BASE}/agreementSpecification", type="http", auth="public", methods=["GET"], csrf=False)
    def list_agreement_spec(self, **params):
        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        env = request.env["tmf.agreement.specification"].sudo()
        recs = env.search([], limit=limit, offset=offset, order="id asc")
        total = env.search_count([])
        payload = [r.to_tmf_json() for r in recs]
        return _json_response(payload, status=200, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(payload))),
        ])

    @http.route(f"{API_BASE}/agreementSpecification/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def retrieve_agreement_spec(self, tmf_id, **params):
        rec = request.env["tmf.agreement.specification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not found")
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/agreementSpecification", type="http", auth="public", methods=["POST"], csrf=False)
    def create_agreement_spec(self, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON")

        # Mandatory for AgreementSpecification: attachment, name :contentReference[oaicite:6]{index=6}
        missing = _require_fields(data, ["attachment", "name"])
        if missing:
            return _error(400, "Missing mandatory attributes", details={"missing": missing})

        vals = {}
        for tmf_key, odoo_field in AGRSPEC_TMF_TO_ODOO.items():
            if tmf_key in data:
                vals[odoo_field] = data[tmf_key]

        # Default: isBundle False :contentReference[oaicite:7]{index=7}
        if "is_bundle" not in vals:
            vals["is_bundle"] = False

        rec = request.env["tmf.agreement.specification"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/agreementSpecification/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_agreement_spec(self, tmf_id, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON")

        rec = request.env["tmf.agreement.specification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not found")

        # Non-patchable: href, id :contentReference[oaicite:8]{index=8}
        for forbidden in ("id", "href"):
            if forbidden in data:
                return _error(400, f"Non patchable attribute: {forbidden}")

        vals = {}
        for tmf_key, odoo_field in AGRSPEC_TMF_TO_ODOO.items():
            if tmf_key in data:
                vals[odoo_field] = data[tmf_key]

        rec.write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/agreementSpecification/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_agreement_spec(self, tmf_id, **params):
        rec = request.env["tmf.agreement.specification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _error(404, "Not found")
        rec.unlink()
        return request.make_response("", status=204)

    # --------------------------
    # Hub (Notifications)
    # --------------------------
    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **params):
        # TMF: POST /hub with {"callback": "..."} :contentReference[oaicite:9]{index=9}
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing callback")

        # Assuming you already have tmf.hub.subscription model (you call it in your model code)
        subs = request.env["tmf.hub.subscription"].sudo().create([
            {
                "name": f"tmf651-agreement-{callback}",
                "callback": callback,
                "query": data.get("query") or "",
                "api_name": "agreement",
                "event_type": "any",
                "content_type": "application/json",
            },
            {
                "name": f"tmf651-agreement-specification-{callback}",
                "callback": callback,
                "query": data.get("query") or "",
                "api_name": "agreementSpecification",
                "event_type": "any",
                "content_type": "application/json",
            },
        ])
        sub = subs[:1]

        # spec sample returns 201 + Location + body with id/callback/query :contentReference[oaicite:10]{index=10}
        headers = [("Content-Type", "application/json"), ("Location", f"{API_BASE}/hub/{sub.id}")]
        body = {"id": str(sub.id), "callback": callback, "query": data.get("query")}
        return request.make_response(json.dumps(body, ensure_ascii=False), headers=headers, status=201)

    @http.route(f"{API_BASE}/hub/<string:hub_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, hub_id, **params):
        sub = request.env["tmf.hub.subscription"].sudo().browse(int(hub_id)) if str(hub_id).isdigit() else request.env["tmf.hub.subscription"]
        if not sub.exists():
            return _error(404, "Not found")
        siblings = request.env["tmf.hub.subscription"].sudo().search([
            ("callback", "=", sub.callback),
            ("api_name", "in", ["agreement", "agreementSpecification"]),
        ])
        (siblings or sub).unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/listener/agreementCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_create(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_attr(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_state(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_delete(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementSpecificationCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_spec_create(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementSpecificationAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_spec_attr(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementSpecificationStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_spec_state(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/agreementSpecificationDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_agreement_spec_delete(self, **params):
        return self._listener_ok()
