# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


API_BASE = "/tmf-api/partyRoleManagement/v5"
RESOURCE = "partyRole"
BASE_PATH = f"{API_BASE}/{RESOURCE}"
ALWAYS_INCLUDE = {"@type", "id", "href"}  # CTK requires @type even in fields mode


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _error(status, reason, code=None, details=None):
    # Keep it simple and consistent. (If you already have a TMF error helper, use that.)
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


def _select_fields(obj, fields_csv):
    if not fields_csv:
        return obj

    wanted = {f.strip() for f in fields_csv.split(",") if f.strip()}
    wanted |= ALWAYS_INCLUDE

    filtered = {k: v for k, v in obj.items() if k in wanted}

    # hard guarantee
    if "@type" not in filtered and "@type" in obj:
        filtered["@type"] = obj["@type"]
    if "id" not in filtered and "id" in obj:
        filtered["id"] = obj["id"]
    if "href" not in filtered and "href" in obj:
        filtered["href"] = obj["href"]

    return filtered


def _require(data, path):
    """
    Validate presence of nested required fields.
    path examples: "engagedParty", "engagedParty.@type", "engagedParty.id", "name", "@type"
    """
    if "." not in path:
        if path not in data or data.get(path) in (None, "", []):
            return False
        return True

    head, tail = path.split(".", 1)
    sub = data.get(head)
    if not isinstance(sub, dict):
        return False
    if tail not in sub or sub.get(tail) in (None, "", []):
        return False
    return True


class TMFPartyRoleController(http.Controller):
    def _listener_ok(self):
        data = _parse_json_body()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    # List or find PartyRole objects: GET /partyRole?fields=...
    @http.route(BASE_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_party_roles(self, **params):
        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        domain = []
        if params.get("name"):
            domain.append(("name", "=", params["name"]))

        env = request.env["tmf.party.role"].sudo()
        records = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)
        payload = [r.to_tmf_json() for r in records]

        fields_csv = params.get("fields")
        if fields_csv:
            payload = [_select_fields(p, fields_csv) for p in payload]

        return _json_response(payload, status=200, headers=[("X-Total-Count", str(total)), ("X-Result-Count", str(len(payload)))])


    # Retrieves a PartyRole by ID: GET /partyRole/{id}?fields=...
    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_party_role(self, rid, **params):
        rec = request.env["tmf.party.role"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"PartyRole {rid} not found")

        obj = rec.to_tmf_json()
        obj = _select_fields(obj, params.get("fields"))
        return _json_response(obj, status=200)

    # Creates a PartyRole: POST /partyRole
    @http.route(BASE_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_party_role(self, **params):
        data = _parse_json_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        # Mandatory Attributes (doc): engagedParty, engagedParty.@type, engagedParty.id, name, @type
        # :contentReference[oaicite:7]{index=7}
        required = ["engagedParty", "engagedParty.@type", "engagedParty.id", "name", "@type"]
        missing = [p for p in required if not _require(data, p)]
        if missing:
            return _error(
                400,
                "Missing mandatory attributes",
                code="TMF669_MANDATORY_ATTRIBUTE_MISSING",
                details={"missing": missing},
            )

        # Build vals (store complex structures as JSON strings in the model)
        vals = {
            "type_name": data.get("@type"),
            "name": data.get("name"),
            "role": data.get("role"),
            "status": data.get("status"),
            "status_reason": data.get("statusReason"),
            "engaged_party_json": json.dumps(data.get("engagedParty"), ensure_ascii=False),
            "party_role_spec_json": json.dumps(data.get("partyRoleSpecification"), ensure_ascii=False)
            if data.get("partyRoleSpecification") is not None
            else False,
            "account_json": json.dumps(data.get("account"), ensure_ascii=False) if data.get("account") is not None else False,
            "agreement_json": json.dumps(data.get("agreement"), ensure_ascii=False) if data.get("agreement") is not None else False,
            "characteristic_json": json.dumps(data.get("characteristic"), ensure_ascii=False)
            if data.get("characteristic") is not None
            else False,
            "contact_medium_json": json.dumps(data.get("contactMedium"), ensure_ascii=False)
            if data.get("contactMedium") is not None
            else False,
            "credit_profile_json": json.dumps(data.get("creditProfile"), ensure_ascii=False)
            if data.get("creditProfile") is not None
            else False,
            "payment_method_json": json.dumps(data.get("paymentMethod"), ensure_ascii=False)
            if data.get("paymentMethod") is not None
            else False,
            "related_party_json": json.dumps(data.get("relatedParty"), ensure_ascii=False)
            if data.get("relatedParty") is not None
            else False,
            "valid_for_json": json.dumps(data.get("validFor"), ensure_ascii=False) if data.get("validFor") is not None else False,
        }

        rec = request.env["tmf.party.role"].sudo().create(vals)

        obj = rec.to_tmf_json()
        obj = _select_fields(obj, params.get("fields"))

        # Response 201 with Location header (doc shows 201 + href in response). :contentReference[oaicite:8]{index=8}
        headers = [("Content-Type", "application/json"), ("Location", rec.href or obj.get("href", ""))]
        return request.make_response(json.dumps(obj, ensure_ascii=False), headers=headers, status=201)
    
    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_party_role(self, rid, **params):
        rec = request.env["tmf.party.role"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"PartyRole {rid} not found")

        data = _parse_json_body()
        if data is None or not isinstance(data, dict):
            return _error(400, "Invalid JSON body")

        # map PATCH keys to model fields
        vals = {}
        if "@type" in data:
            vals["type_name"] = data.get("@type")
        if "name" in data:
            vals["name"] = data.get("name")
        if "role" in data:
            vals["role"] = data.get("role")
        if "status" in data:
            vals["status"] = data.get("status")
        if "statusReason" in data:
            vals["status_reason"] = data.get("statusReason")

        # nested objects (store as JSON)
        if "engagedParty" in data:
            vals["engaged_party_json"] = json.dumps(data.get("engagedParty"), ensure_ascii=False)
        if "partyRoleSpecification" in data:
            vals["party_role_spec_json"] = json.dumps(data.get("partyRoleSpecification"), ensure_ascii=False)

        # extend similarly if CTK later expects more patchable attributes

        if vals:
            rec.write(vals)

        obj = rec.to_tmf_json()
        obj = _select_fields(obj, params.get("fields"))
        return _json_response(obj, status=200)


    # Deletes a PartyRole: DELETE /partyRole/{id}
    @http.route(f"{BASE_PATH}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_party_role(self, rid, **params):
        rec = request.env["tmf.party.role"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, f"PartyRole {rid} not found")

        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **params):
        data = _parse_json_body()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf669-party-role-{callback}",
            "api_name": "partyRole",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": "any",
            "content_type": "application/json",
        })
        return _json_response({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}, status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "partyRole":
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/listener/partyRoleCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_create(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleAttributeValueChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_attr(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleStateChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_state(self, **params):
        return self._listener_ok()

    @http.route(f"{API_BASE}/listener/partyRoleDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_party_role_delete(self, **params):
        return self._listener_ok()
