# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

API_BASE = "/tmf-api/accountManagement/v5"

ACCOUNT_RESOURCES = {
    "partyAccount": "PartyAccount",
    "billingAccount": "BillingAccount",
    "financialAccount": "FinancialAccount",
    "settlementAccount": "SettlementAccount",
}

EXTRA_RESOURCES = {
    "billFormat": {"model": "tmf.bill.format", "type": "BillFormat"},
    "billingCycleSpecification": {"model": "tmf.billing.cycle.spec", "type": "BillingCycleSpecification"},
    "billPresentationMedia": {"model": "tmf.bill.presentation.media", "type": "BillPresentationMedia"},
}

IMMUTABLE_KEYS = {"id", "href", "@type", "@baseType", "@schemaLocation", "lastUpdate", "lastModified"}


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=[("Content-Type", "application/json")],
        status=status,
    )


def _error(status, reason, details=None):
    body = {"error": {"status": status, "reason": reason}}
    if details is not None:
        body["error"]["details"] = details
    return _json_response(body, status=status)


def _parse_body():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _apply_fields(obj, fields_param):
    """
    CTK expects id/href/@type even when fields=name
    """
    if not fields_param:
        return obj
    wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
    always = {"@type", "id", "href"}
    wanted_set = set(wanted) | always
    return {k: v for k, v in obj.items() if k in wanted_set}


def _domain_from_query_params(params):
    domain = []
    if params.get("name"):
        domain.append(("name", "=", params["name"]))
    return domain


def _validate_patch_immutables(data, current_json):
    """
    Allow immutable keys in PATCH if they match current values.
    Only fail if they try to change them.
    """
    bad = []
    for k in data.keys():
        if k in IMMUTABLE_KEYS:
            if k in current_json and data.get(k) not in (None, "") and data.get(k) != current_json.get(k):
                bad.append(k)
    return bad


def _tmf_to_odoo_vals_account(data):
    vals = {}

    if "name" in data:
        vals["name"] = data["name"]
    if "description" in data:
        vals["description"] = data.get("description") or ""
    if "accountType" in data:
        vals["account_type"] = data.get("accountType") or ""
    if "state" in data:
        vals["state"] = data.get("state") or ""
    if "paymentStatus" in data:
        vals["payment_status"] = data.get("paymentStatus") or ""
    if "ratingType" in data:
        vals["rating_type"] = data.get("ratingType") or ""

    for key, field_name in [
        ("relatedParty", "related_party_json"),
        ("creditLimit", "credit_limit_json"),
        ("accountBalance", "account_balance_json"),
        ("accountRelationship", "account_relationship_json"),
        ("contact", "contact_json"),
        ("taxExemption", "tax_exemption_json"),
        ("financialAccount", "financial_account_json"),
        ("billStructure", "bill_structure_json"),
        ("defaultPaymentMethod", "default_payment_method_json"),
        ("paymentPlan", "payment_plan_json"),
    ]:
        if key in data:
            vals[field_name] = json.dumps(data[key], ensure_ascii=False)

    return vals


def _validate_post_mandatory_account(data, expected_type):
    missing = []
    if not isinstance(data, dict):
        return ["<body>"]

    if data.get("@type") != expected_type:
        missing.append("@type (must be '%s')" % expected_type)

    if not data.get("name"):
        missing.append("name")

    rp = data.get("relatedParty")
    if not isinstance(rp, list) or len(rp) == 0:
        missing.append("relatedParty (non-empty array)")
    else:
        for i, item in enumerate(rp):
            if not isinstance(item, dict):
                missing.append(f"relatedParty[{i}] (object)")
                continue
            if not item.get("@type"):
                missing.append(f"relatedParty[{i}].@type")
            if not item.get("role"):
                missing.append(f"relatedParty[{i}].role")

    return missing


def _validate_post_mandatory_simple(data, expected_type):
    missing = []
    if not isinstance(data, dict):
        return ["<body>"]
    if data.get("@type") != expected_type:
        missing.append("@type (must be '%s')" % expected_type)
    if not data.get("name"):
        missing.append("name")
    return missing


class TMF666Controller(http.Controller):
    # -------- LIST --------
    @http.route(f"{API_BASE}/<string:resource>", type="http", auth="public", methods=["GET"], csrf=False)
    def list_resource(self, resource, **params):
        if resource in ACCOUNT_RESOURCES:
            rtype = ACCOUNT_RESOURCES[resource]
            recs = request.env["tmf.account"].sudo().search(
                [("resource_type", "=", rtype)] + _domain_from_query_params(params)
            )
            return _json_response([_apply_fields(r.to_tmf_json(), params.get("fields")) for r in recs], status=200)

        if resource in EXTRA_RESOURCES:
            model = EXTRA_RESOURCES[resource]["model"]
            recs = request.env[model].sudo().search(_domain_from_query_params(params))
            return _json_response([_apply_fields(r.to_tmf_json(), params.get("fields")) for r in recs], status=200)

        return _error(404, f"Unknown resource '{resource}'")

    # -------- GET by ID --------
    @http.route(f"{API_BASE}/<string:resource>/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource(self, resource, rid, **params):
        if resource in ACCOUNT_RESOURCES:
            rtype = ACCOUNT_RESOURCES[resource]
            rec = request.env["tmf.account"].sudo().search(
                [("resource_type", "=", rtype), ("tmf_id", "=", rid)], limit=1
            )
            if not rec:
                return _error(404, "Not found")
            return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

        if resource in EXTRA_RESOURCES:
            model = EXTRA_RESOURCES[resource]["model"]
            rec = request.env[model].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not rec:
                return _error(404, "Not found")
            return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

        return _error(404, f"Unknown resource '{resource}'")

    # -------- POST --------
    @http.route(f"{API_BASE}/<string:resource>", type="http", auth="public", methods=["POST"], csrf=False)
    def create_resource(self, resource, **params):
        data = _parse_body()
        if data is None:
            return _error(400, "Invalid JSON body")

        # EXTRA resources
        if resource in EXTRA_RESOURCES:
            expected_type = EXTRA_RESOURCES[resource]["type"]
            missing = _validate_post_mandatory_simple(data, expected_type)
            if missing:
                return _error(400, "Missing/invalid mandatory attributes", details=missing)

            model = EXTRA_RESOURCES[resource]["model"]
            vals = {"name": data["name"], "description": data.get("description") or ""}

            if expected_type == "BillingCycleSpecification":
                for k, f in [
                    ("frequency", "frequency"),
                    ("billingPeriod", "billing_period"),
                    ("billingDateShift", "billing_date_shift"),
                    ("chargeDateOffset", "charge_date_offset"),
                    ("creditDateOffset", "credit_date_offset"),
                    ("mailingDateOffset", "mailing_date_offset"),
                    ("paymentDueDateOffset", "payment_due_date_offset"),
                ]:
                    if k in data:
                        vals[f] = data[k]
                if "validFor" in data:
                    vals["valid_for_json"] = json.dumps(data["validFor"], ensure_ascii=False)

            rec = request.env[model].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        # ACCOUNT resources
        if resource in ACCOUNT_RESOURCES:
            expected_type = ACCOUNT_RESOURCES[resource]
            missing = _validate_post_mandatory_account(data, expected_type)
            if missing:
                return _error(400, "Missing/invalid mandatory attributes", details=missing)

            vals = _tmf_to_odoo_vals_account(data)
            vals["resource_type"] = expected_type
            rec = request.env["tmf.account"].sudo().create(vals)
            return _json_response(rec.to_tmf_json(), status=201)

        return _error(404, f"Unknown resource '{resource}'")

    # -------- PATCH --------
    @http.route(f"{API_BASE}/<string:resource>/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_resource(self, resource, rid, **params):
        data = _parse_body()
        if data is None or not isinstance(data, dict):
            return _error(400, "Invalid JSON body")

        # EXTRA resources
        if resource in EXTRA_RESOURCES:
            model = EXTRA_RESOURCES[resource]["model"]
            expected_type = EXTRA_RESOURCES[resource]["type"]
            rec = request.env[model].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not rec:
                return _error(404, "Not found")

            current = rec.to_tmf_json()
            bad = _validate_patch_immutables(data, current)
            if bad:
                return _error(400, "Attempt to change non-patchable attributes", details=bad)

            if "@type" in data and data["@type"] != expected_type:
                return _error(400, "@type must match resource")
            data.pop("@type", None)

            for k in list(data.keys()):
                if k in IMMUTABLE_KEYS:
                    data.pop(k, None)

            vals = {}
            if "name" in data:
                vals["name"] = data["name"]
            if "description" in data:
                vals["description"] = data.get("description") or ""

            # IMPORTANT: allow PATCH of BillingCycleSpecification patchable fields
            if expected_type == "BillingCycleSpecification":
                for k, f in [
                    ("frequency", "frequency"),
                    ("billingPeriod", "billing_period"),
                    ("billingDateShift", "billing_date_shift"),
                    ("chargeDateOffset", "charge_date_offset"),
                    ("creditDateOffset", "credit_date_offset"),
                    ("mailingDateOffset", "mailing_date_offset"),
                    ("paymentDueDateOffset", "payment_due_date_offset"),
                ]:
                    if k in data:
                        vals[f] = data[k]
                if "validFor" in data:
                    vals["valid_for_json"] = json.dumps(data["validFor"], ensure_ascii=False)

            rec.write(vals)
            return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

        # ACCOUNT resources
        if resource in ACCOUNT_RESOURCES:
            rtype = ACCOUNT_RESOURCES[resource]
            rec = request.env["tmf.account"].sudo().search(
                [("resource_type", "=", rtype), ("tmf_id", "=", rid)], limit=1
            )
            if not rec:
                return _error(404, "Not found")

            current = rec.to_tmf_json()
            bad = _validate_patch_immutables(data, current)
            if bad:
                return _error(400, "Attempt to change non-patchable attributes", details=bad)

            if "@type" in data and data["@type"] != rtype:
                return _error(400, "@type must match resource")
            data.pop("@type", None)

            for k in list(data.keys()):
                if k in IMMUTABLE_KEYS:
                    data.pop(k, None)

            vals = _tmf_to_odoo_vals_account(data)
            rec.write(vals)
            return _json_response(_apply_fields(rec.to_tmf_json(), params.get("fields")), status=200)

        return _error(404, f"Unknown resource '{resource}'")

    # -------- DELETE --------
    @http.route(f"{API_BASE}/<string:resource>/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_resource(self, resource, rid, **params):
        if resource in EXTRA_RESOURCES:
            model = EXTRA_RESOURCES[resource]["model"]
            rec = request.env[model].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not rec:
                return _error(404, "Not found")
            rec.unlink()
            return _json_response({}, status=204)

        if resource in ACCOUNT_RESOURCES:
            rtype = ACCOUNT_RESOURCES[resource]
            rec = request.env["tmf.account"].sudo().search(
                [("resource_type", "=", rtype), ("tmf_id", "=", rid)], limit=1
            )
            if not rec:
                return _error(404, "Not found")
            rec.unlink()
            return _json_response({}, status=204)

        return _error(404, f"Unknown resource '{resource}'")
