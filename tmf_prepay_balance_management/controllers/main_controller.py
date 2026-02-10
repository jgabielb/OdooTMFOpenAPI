# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import uuid
from datetime import datetime, timezone

API_BASE = "/tmf-api/prepayBalanceManagement/v4"

# -------------------------
# Helpers
# -------------------------
def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _safe_parse_dt(s):
    try:
        if not s:
            return None
        s = str(s).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


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
    except Exception as e:
        raise ValueError(f"Invalid JSON body: {e}")

def _merge_patch(original: dict, patch: dict) -> dict:
    """
    JSON Merge Patch (RFC 7386)
    - if patch value is null => delete key
    - if patch value is object => recursively merge
    - else => replace
    """
    if not isinstance(patch, dict):
        return patch
    if not isinstance(original, dict):
        original = {}
    out = dict(original)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict):
            out[k] = _merge_patch(out.get(k), v)
        else:
            out[k] = v
    return out

def _make_href(resource, rid):
    return f"{API_BASE}/{resource}/{rid}"

def _fields_filter(obj: dict, fields_param):
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in wanted}

def _safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default

# -------------------------
# Serializers (model -> TMF JSON)
# -------------------------
def _bucket_to_json(rec):
    data = {
        "id": rec.tmf_id,
        "href": rec.href or _make_href("bucket", rec.tmf_id),
        "@type": rec.type or "Bucket",
        "@baseType": rec.base_type,
        "@schemaLocation": rec.schema_location,
        "description": rec.description,
        "name": rec.name,
        "isShared": rec.is_shared,
        "usageType": rec.usage_type,
        "status": rec.status or "active",
        "remainingValue": {"amount": rec.remaining_amount, "units": rec.remaining_units} if rec.remaining_units else None,
        "remainingValueName": rec.remaining_value_name,
        "reservedValue": {"amount": rec.reserved_amount, "units": rec.reserved_units} if rec.reserved_units else None,
        "validFor": {
            "startDateTime": rec.valid_for_start.isoformat() if rec.valid_for_start else None,
            "endDateTime": rec.valid_for_end.isoformat() if rec.valid_for_end else None,
        },
        "partyAccount": json.loads(rec.party_account_json) if rec.party_account_json else None,
        "product": json.loads(rec.product_json) if rec.product_json else None,
        "logicalResource": json.loads(rec.logical_resource_json) if rec.logical_resource_json else None,
        "relatedParty": json.loads(rec.related_party_json) if rec.related_party_json else None,
        "requestedDate": rec.requested_date.isoformat() if rec.requested_date else None,
        "confirmationDate": rec.confirmation_date.isoformat() if rec.confirmation_date else None,
    }
    # remove nulls
    return {k: v for k, v in data.items() if v is not None}

def _topup_to_json(rec):
    data = {
        "id": rec.tmf_id,
        "href": rec.href or _make_href("topupBalance", rec.tmf_id),
        "@type": rec.type or "TopupBalance",
        "description": rec.description,
        "reason": rec.reason,
        "status": rec.status,
        "usageType": rec.usage_type,
        "requestedDate": rec.requested_date.isoformat() if rec.requested_date else None,
        "confirmationDate": rec.confirmation_date.isoformat() if rec.confirmation_date else None,
        "amount": {"amount": rec.amount_value, "units": rec.amount_units} if rec.amount_units else None,
        "isAutoTopup": rec.is_auto_topup,
        "numberOfPeriods": rec.number_of_periods,
        "recurringPeriod": rec.recurring_period,
        "voucher": rec.voucher,
        "bucket": json.loads(rec.bucket_json) if rec.bucket_json else None,
        "impactedBucket": json.loads(rec.impacted_bucket_json) if rec.impacted_bucket_json else None,
        "channel": json.loads(rec.channel_json) if rec.channel_json else None,
        "payment": json.loads(rec.payment_json) if rec.payment_json else None,
        "paymentMethod": json.loads(rec.payment_method_json) if rec.payment_method_json else None,
        "partyAccount": json.loads(rec.party_account_json) if rec.party_account_json else None,
        "product": json.loads(rec.product_json) if rec.product_json else None,
        "logicalResource": json.loads(rec.logical_resource_json) if rec.logical_resource_json else None,
        "relatedParty": json.loads(rec.related_party_json) if rec.related_party_json else None,
        "requestor": json.loads(rec.requestor_json) if rec.requestor_json else None,
    }
    return {k: v for k, v in data.items() if v is not None}

def _adjust_to_json(rec):
    data = {
        "id": rec.tmf_id,
        "href": rec.href or _make_href("adjustBalance", rec.tmf_id),
        "@type": rec.type or "AdjustBalance",
        "description": rec.description,
        "reason": rec.reason,
        "status": rec.status,
        "usageType": rec.usage_type,
        "requestedDate": rec.requested_date.isoformat() if rec.requested_date else None,
        "confirmationDate": rec.confirmation_date.isoformat() if rec.confirmation_date else None,
        "adjustType": rec.adjust_type,
        "amount": {"amount": rec.amount_value, "units": rec.amount_units} if rec.amount_units else None,
        "bucket": json.loads(rec.bucket_json) if rec.bucket_json else None,
        "impactedBucket": json.loads(rec.impacted_bucket_json) if rec.impacted_bucket_json else None,
        "channel": json.loads(rec.channel_json) if rec.channel_json else None,
        "partyAccount": json.loads(rec.party_account_json) if rec.party_account_json else None,
        "product": json.loads(rec.product_json) if rec.product_json else None,
        "logicalResource": json.loads(rec.logical_resource_json) if rec.logical_resource_json else None,
        "relatedParty": json.loads(rec.related_party_json) if rec.related_party_json else None,
        "requestor": json.loads(rec.requestor_json) if rec.requestor_json else None,
    }
    return {k: v for k, v in data.items() if v is not None}


def _reserve_to_json(rec):
    data = {
        "id": rec.tmf_id,
        "href": rec.href or _make_href("reserveBalance", rec.tmf_id),
        "@type": rec.type or "ReserveBalance",
        "description": rec.description,
        "reason": rec.reason,
        "status": rec.status,
        "usageType": rec.usage_type,
        "requestedDate": rec.requested_date.isoformat() if rec.requested_date else None,
        "confirmationDate": rec.confirmation_date.isoformat() if rec.confirmation_date else None,
        "amount": {"amount": rec.amount_value, "units": rec.amount_units} if rec.amount_units else None,
        "bucket": json.loads(rec.bucket_json) if rec.bucket_json else None,
        "impactedBucket": json.loads(rec.impacted_bucket_json) if rec.impacted_bucket_json else None,
        "channel": json.loads(rec.channel_json) if rec.channel_json else None,
        "partyAccount": json.loads(rec.party_account_json) if rec.party_account_json else None,
        "product": json.loads(rec.product_json) if rec.product_json else None,
        "logicalResource": json.loads(rec.logical_resource_json) if rec.logical_resource_json else None,
        "relatedParty": json.loads(rec.related_party_json) if rec.related_party_json else None,
        "requestor": json.loads(rec.requestor_json) if rec.requestor_json else None,
    }
    return {k: v for k, v in data.items() if v is not None}


# -------------------------
# Controllers
# -------------------------
class TMF654Controller(http.Controller):

    # -------- Bucket --------
    @http.route(f"{API_BASE}/bucket", type="http", auth="public", methods=["GET"], csrf=False)
    def list_bucket(self, **params):
        domain = []
        if params.get("usageType"):
            domain.append(("usage_type", "=", params["usageType"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))

        recs = request.env["tmf654.bucket"].sudo().search(domain, limit=int(params.get("limit", 100)), offset=int(params.get("offset", 0)))
        items = [_fields_filter(_bucket_to_json(r), params.get("fields")) for r in recs]
        return _json_response(items, 200)

    @http.route(f"{API_BASE}/bucket/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_bucket(self, rid, **params):
        rec = request.env["tmf654.bucket"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Bucket not found")
        return _json_response(_fields_filter(_bucket_to_json(rec), params.get("fields")), 200)

    @http.route(f"{API_BASE}/bucket", type="http", auth="public", methods=["POST"], csrf=False)
    def create_bucket(self, **params):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        if not body.get("usageType"):
            return _error(400, "usageType is mandatory for Bucket")

        rid = body.get("id") or str(uuid.uuid4())
        href = body.get("href") or _make_href("bucket", rid)

        remaining = body.get("remainingValue") or {}
        reserved = body.get("reservedValue") or {}
        valid_for = body.get("validFor") or {}

        vals = {
            "tmf_id": rid,
            "href": href,
            "type": body.get("@type") or "Bucket",
            "base_type": body.get("@baseType"),
            "schema_location": body.get("@schemaLocation"),
            "description": body.get("description"),
            "name": body.get("name") or rid,
            "is_shared": bool(body.get("isShared", False)),
            "usage_type": body.get("usageType"),
            "status": body.get("status") or "active",
            "remaining_amount": _safe_float(remaining.get("amount"), 0.0),
            "remaining_units": remaining.get("units"),
            "reserved_amount": _safe_float(reserved.get("amount"), 0.0),
            "reserved_units": reserved.get("units"),
            "requested_date": request.env.cr.now(),
            "confirmation_date": request.env.cr.now(),
        }

        # parse validFor dates (keep simple; optional)
        # you can later add robust parsing
        if isinstance(valid_for, dict):
            vals["valid_for_start"] = _safe_parse_dt(valid_for.get("startDateTime"))
            vals["valid_for_end"] = _safe_parse_dt(valid_for.get("endDateTime"))

        # JSON refs
        for k, field in [
            ("partyAccount", "party_account_json"),
            ("product", "product_json"),
            ("logicalResource", "logical_resource_json"),
            ("relatedParty", "related_party_json"),
        ]:
            if body.get(k) is not None:
                vals[field] = json.dumps(body.get(k), ensure_ascii=False)

        rec = request.env["tmf654.bucket"].sudo().create(vals)
        return _json_response(_bucket_to_json(rec), 201)

    @http.route(f"{API_BASE}/bucket/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_bucket(self, rid, **params):
        rec = request.env["tmf654.bucket"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "Bucket not found")
        rec.unlink()
        return request.make_response("", status=204)

    # -------- TopupBalance --------
    @http.route(f"{API_BASE}/topupBalance", type="http", auth="public", methods=["GET"], csrf=False)
    def list_topup(self, **params):
        recs = request.env["tmf654.topup.balance"].sudo().search([], limit=int(params.get("limit", 100)), offset=int(params.get("offset", 0)))
        items = [_fields_filter(_topup_to_json(r), params.get("fields")) for r in recs]
        return _json_response(items, 200)

    @http.route(f"{API_BASE}/topupBalance/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_topup(self, rid, **params):
        rec = request.env["tmf654.topup.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "TopupBalance not found")
        return _json_response(_fields_filter(_topup_to_json(rec), params.get("fields")), 200)

    @http.route(f"{API_BASE}/topupBalance", type="http", auth="public", methods=["POST"], csrf=False)
    def create_topup(self, **params):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        # Spec use case: amount is mandatory :contentReference[oaicite:14]{index=14}
        amount = body.get("amount")
        if not isinstance(amount, dict) or amount.get("amount") is None or not amount.get("units"):
            return _error(400, "amount.amount and amount.units are mandatory for TopupBalance")

        # Spec use case: at least one identifier MUST be included (bucketRef/productRef/logicalResourceRef/relatedParty...) :contentReference[oaicite:15]{index=15}
        has_identifier = any(body.get(k) is not None for k in ["bucket", "product", "logicalResource", "relatedParty", "partyAccount"])
        if not has_identifier:
            return _error(400, "At least one of bucket/product/logicalResource/relatedParty/partyAccount must be provided")

        rid = body.get("id") or str(uuid.uuid4())
        href = body.get("href") or _make_href("topupBalance", rid)

        vals = {
            "tmf_id": rid,
            "href": href,
            "type": body.get("@type") or "TopupBalance",
            "description": body.get("description"),
            "reason": body.get("reason"),
            "status": body.get("status") or "requested",
            "usage_type": body.get("usageType"),
            "requested_date": request.env.cr.now(),
            "amount_value": _safe_float(amount.get("amount"), 0.0),
            "amount_units": amount.get("units"),
            "is_auto_topup": bool(body.get("isAutoTopup", False)),
            "number_of_periods": body.get("numberOfPeriods"),
            "recurring_period": body.get("recurringPeriod"),
            "voucher": body.get("voucher"),
        }

        for k, field in [
            ("bucket", "bucket_json"),
            ("impactedBucket", "impacted_bucket_json"),
            ("channel", "channel_json"),
            ("payment", "payment_json"),
            ("paymentMethod", "payment_method_json"),
            ("partyAccount", "party_account_json"),
            ("product", "product_json"),
            ("logicalResource", "logical_resource_json"),
            ("relatedParty", "related_party_json"),
            ("requestor", "requestor_json"),
        ]:
            if body.get(k) is not None:
                vals[field] = json.dumps(body.get(k), ensure_ascii=False)

        rec = request.env["tmf654.topup.balance"].sudo().create(vals)

        # simulate confirmation (optional): in real life, async
        rec.sudo().write({"status": rec.status or "confirmed", "confirmation_date": request.env.cr.now()})

        return _json_response(_topup_to_json(rec), 201)

    @http.route(f"{API_BASE}/topupBalance/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_topup(self, rid, **params):
        rec = request.env["tmf654.topup.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "TopupBalance not found")

        try:
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        current = _topup_to_json(rec)
        merged = _merge_patch(current, patch)

        # Common cancel use case: status -> cancelled :contentReference[oaicite:16]{index=16}
        if "status" in merged and merged["status"] == "cancelled":
            rec.write({"status": "cancelled"})
            return _json_response(_topup_to_json(rec), 200)

        # Otherwise allow minimal safe updates
        if "reason" in merged:
            rec.write({"reason": merged.get("reason")})
        if "description" in merged:
            rec.write({"description": merged.get("description")})

        return _json_response(_topup_to_json(rec), 200)

    @http.route(f"{API_BASE}/topupBalance/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_topup(self, rid, **params):
        rec = request.env["tmf654.topup.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "TopupBalance not found")
        rec.unlink()
        return _json_response({}, 204)
    
    # -------- AdjustBalance --------
    @http.route(f"{API_BASE}/adjustBalance", type="http", auth="public", methods=["GET"], csrf=False)
    def list_adjust(self, **params):
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        if params.get("usageType"):
            domain.append(("usage_type", "=", params["usageType"]))

        recs = request.env["tmf654.adjust.balance"].sudo().search(
            domain,
            limit=int(params.get("limit", 100)),
            offset=int(params.get("offset", 0)),
        )
        items = [_fields_filter(_adjust_to_json(r), params.get("fields")) for r in recs]
        return _json_response(items, 200)

    @http.route(f"{API_BASE}/adjustBalance/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_adjust(self, rid, **params):
        rec = request.env["tmf654.adjust.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "AdjustBalance not found")
        return _json_response(_fields_filter(_adjust_to_json(rec), params.get("fields")), 200)

    @http.route(f"{API_BASE}/adjustBalance", type="http", auth="public", methods=["POST"], csrf=False)
    def create_adjust(self, **params):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        amount = body.get("amount")
        if not isinstance(amount, dict) or amount.get("amount") is None or not amount.get("units"):
            return _error(400, "amount.amount and amount.units are mandatory for AdjustBalance")

        has_identifier = any(body.get(k) is not None for k in ["bucket", "product", "logicalResource", "relatedParty", "partyAccount"])
        if not has_identifier:
            return _error(400, "At least one of bucket/product/logicalResource/relatedParty/partyAccount must be provided")

        rid = body.get("id") or str(uuid.uuid4())
        href = body.get("href") or _make_href("adjustBalance", rid)

        vals = {
            "tmf_id": rid,
            "href": href,
            "type": body.get("@type") or "AdjustBalance",
            "description": body.get("description"),
            "reason": body.get("reason"),
            "status": body.get("status") or "requested",
            "usage_type": body.get("usageType"),
            "adjust_type": body.get("adjustType"),
            "requested_date": request.env.cr.now(),
            "confirmation_date": request.env.cr.now(),
            "amount_value": _safe_float(amount.get("amount"), 0.0),
            "amount_units": amount.get("units"),
        }

        for k, field in [
            ("bucket", "bucket_json"),
            ("impactedBucket", "impacted_bucket_json"),
            ("channel", "channel_json"),
            ("partyAccount", "party_account_json"),
            ("product", "product_json"),
            ("logicalResource", "logical_resource_json"),
            ("relatedParty", "related_party_json"),
            ("requestor", "requestor_json"),
        ]:
            if body.get(k) is not None:
                vals[field] = json.dumps(body.get(k), ensure_ascii=False)

        rec = request.env["tmf654.adjust.balance"].sudo().create(vals)
        return _json_response(_adjust_to_json(rec), 201)

    @http.route(f"{API_BASE}/adjustBalance/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_adjust(self, rid, **params):
        rec = request.env["tmf654.adjust.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "AdjustBalance not found")

        try:
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        current = _adjust_to_json(rec)
        merged = _merge_patch(current, patch)

        if merged.get("status") == "cancelled":
            rec.write({"status": "cancelled"})
            return _json_response(_adjust_to_json(rec), 200)

        # minimal safe updates
        if "reason" in merged:
            rec.write({"reason": merged.get("reason")})
        if "description" in merged:
            rec.write({"description": merged.get("description")})

        return _json_response(_adjust_to_json(rec), 200)

    @http.route(f"{API_BASE}/adjustBalance/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_adjust(self, rid, **params):
        rec = request.env["tmf654.adjust.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "AdjustBalance not found")
        rec.unlink()
        return request.make_response("", status=204)


    # -------- ReserveBalance --------
    @http.route(f"{API_BASE}/reserveBalance", type="http", auth="public", methods=["GET"], csrf=False)
    def list_reserve(self, **params):
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        if params.get("usageType"):
            domain.append(("usage_type", "=", params["usageType"]))

        recs = request.env["tmf654.reserve.balance"].sudo().search(
            domain,
            limit=int(params.get("limit", 100)),
            offset=int(params.get("offset", 0)),
        )
        items = [_fields_filter(_reserve_to_json(r), params.get("fields")) for r in recs]
        return _json_response(items, 200)

    @http.route(f"{API_BASE}/reserveBalance/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_reserve(self, rid, **params):
        rec = request.env["tmf654.reserve.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "ReserveBalance not found")
        return _json_response(_fields_filter(_reserve_to_json(rec), params.get("fields")), 200)

    @http.route(f"{API_BASE}/reserveBalance", type="http", auth="public", methods=["POST"], csrf=False)
    def create_reserve(self, **params):
        try:
            body = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        amount = body.get("amount")
        if not isinstance(amount, dict) or amount.get("amount") is None or not amount.get("units"):
            return _error(400, "amount.amount and amount.units are mandatory for ReserveBalance")

        has_identifier = any(body.get(k) is not None for k in ["bucket", "product", "logicalResource", "relatedParty", "partyAccount"])
        if not has_identifier:
            return _error(400, "At least one of bucket/product/logicalResource/relatedParty/partyAccount must be provided")

        rid = body.get("id") or str(uuid.uuid4())
        href = body.get("href") or _make_href("reserveBalance", rid)

        vals = {
            "tmf_id": rid,
            "href": href,
            "type": body.get("@type") or "ReserveBalance",
            "description": body.get("description"),
            "reason": body.get("reason"),
            "status": body.get("status") or "requested",
            "usage_type": body.get("usageType"),
            "requested_date": request.env.cr.now(),
            "confirmation_date": request.env.cr.now(),
            "amount_value": _safe_float(amount.get("amount"), 0.0),
            "amount_units": amount.get("units"),
        }

        for k, field in [
            ("bucket", "bucket_json"),
            ("impactedBucket", "impacted_bucket_json"),
            ("channel", "channel_json"),
            ("partyAccount", "party_account_json"),
            ("product", "product_json"),
            ("logicalResource", "logical_resource_json"),
            ("relatedParty", "related_party_json"),
            ("requestor", "requestor_json"),
        ]:
            if body.get(k) is not None:
                vals[field] = json.dumps(body.get(k), ensure_ascii=False)

        rec = request.env["tmf654.reserve.balance"].sudo().create(vals)
        return _json_response(_reserve_to_json(rec), 201)

    @http.route(f"{API_BASE}/reserveBalance/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_reserve(self, rid, **params):
        rec = request.env["tmf654.reserve.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "ReserveBalance not found")

        try:
            patch = _parse_json_body()
        except ValueError as e:
            return _error(400, str(e))

        current = _reserve_to_json(rec)
        merged = _merge_patch(current, patch)

        if merged.get("status") == "cancelled":
            rec.write({"status": "cancelled"})
            return _json_response(_reserve_to_json(rec), 200)

        if "reason" in merged:
            rec.write({"reason": merged.get("reason")})
        if "description" in merged:
            rec.write({"description": merged.get("description")})

        return _json_response(_reserve_to_json(rec), 200)

    @http.route(f"{API_BASE}/reserveBalance/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_reserve(self, rid, **params):
        rec = request.env["tmf654.reserve.balance"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return _error(404, "ReserveBalance not found")
        rec.unlink()
        return request.make_response("", status=204)

