# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import uuid
from datetime import datetime, timezone


API_BASE = "/tmf-api/quoteManagement/v4"
RESOURCE = "quote"
BASE_PATH = f"{API_BASE}/{RESOURCE}"
HUB_PATH = f"{API_BASE}/hub"


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _empty(status=204, headers=None):
    headers = headers or []
    return request.make_response("", headers=headers, status=status)


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


def _fields_param():
    return request.params.get("fields")


def _parse_dt(value):
    """
    Parse TMF DateTime strings like '2019-05-06T12:45:12.028Z' into Odoo datetime.
    Returns False if empty.
    """
    if not value:
        return False
    try:
        return fields.Datetime.to_datetime(value)
    except Exception:
        return False


def _apply_filters(domain):
    # CTK filters commonly used: id, quoteDate, state (+ keep externalId)
    state = request.params.get("state")
    if state:
        domain.append(("state", "=", state))

    external_id = request.params.get("externalId")
    if external_id:
        domain.append(("tmf_external_id", "=", external_id))

    rid = request.params.get("id")
    if rid:
        domain.append(("tmf_id", "=", rid))

    qd = request.params.get("quoteDate")
    if qd:
        dt = _parse_dt(qd)
        if dt:
            domain.append(("quote_date", "=", dt))

    return domain


def _now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


class TMF648QuoteController(http.Controller):

    # -------------------------
    # Quote CRUD
    # -------------------------
    @http.route(BASE_PATH, methods=["GET"], type="http", auth="public", csrf=False)
    def list_quotes(self, **kwargs):
        domain = _apply_filters([])
        quotes = request.env["tmf.quote"].sudo().search(domain, limit=200)
        fp = _fields_param()
        return _json_response([q.to_tmf_json(fields_param=fp) for q in quotes], status=200)

    @http.route(f"{BASE_PATH}/<string:quote_id>", methods=["GET"], type="http", auth="public", csrf=False)
    def get_quote(self, quote_id, **kwargs):
        q = request.env["tmf.quote"].sudo().search([("tmf_id", "=", quote_id)], limit=1)
        if not q and quote_id.isdigit():
            q = request.env["tmf.quote"].sudo().browse(int(quote_id))
        if not q or not q.exists():
            return _error(404, "Quote not found")
        return _json_response(q.to_tmf_json(fields_param=_fields_param()), status=200)

    @http.route(BASE_PATH, methods=["POST"], type="http", auth="public", csrf=False)
    def create_quote(self, **kwargs):
        try:
            body = _parse_json_body()
            if body is None:
                return _error(400, "Invalid JSON")

            # Enforce mandatory quoteItem (at least one) per spec
            if not body.get("quoteItem"):
                return _error(400, "quoteItem is mandatory and must contain at least one item")

            # Enforce POST forbidden fields per spec (provider sets these)
            forbidden = {"authorization", "effectiveQuoteCompletionDate", "expectedQuoteCompletionDate", "quoteDate"}
            present_forbidden = [f for f in forbidden if f in body and body.get(f) not in (None, [], "")]
            if present_forbidden:
                return _error(400, "Forbidden fields in POST", details={"fields": present_forbidden})

            # Enforce quoteItem forbidden fields in POST
            for idx, qi in enumerate(body.get("quoteItem", []), start=1):
                for f in ("state", "quoteItemAuthorization", "quoteItemPrice"):
                    if f in qi and qi.get(f) not in (None, [], ""):
                        return _error(
                            400,
                            "Forbidden fields in quoteItem during POST",
                            details={"itemIndex": idx, "field": f},
                        )

            instant_sync = bool(body.get("instantSyncQuote", False))
            tmf_id = str(uuid.uuid4())

            vals = {
                "tmf_id": tmf_id,
                "tmf_external_id": body.get("externalId"),
                "category": body.get("category"),
                "description": body.get("description"),
                "requested_quote_completion_date": _parse_dt(body.get("requestedQuoteCompletionDate")),
                "expected_fulfillment_start_date": _parse_dt(body.get("expectedFulfillmentStartDate")),
                "version": body.get("version"),
                "state": body.get("state") or "inProgress",
                "agreement_json": json.dumps(body.get("agreement", []), ensure_ascii=False),
                "billing_account_json": json.dumps(body.get("billingAccount", []), ensure_ascii=False),
                "contact_medium_json": json.dumps(body.get("contactMedium", []), ensure_ascii=False),
                "note_json": json.dumps(body.get("note", []), ensure_ascii=False),
                "related_party_json": json.dumps(body.get("relatedParty", []), ensure_ascii=False),
                "poq_json": json.dumps(body.get("productOfferingQualification", []), ensure_ascii=False),
                "quote_total_price_json": json.dumps(body.get("quoteTotalPrice", []), ensure_ascii=False),
                "valid_for_json": json.dumps(body.get("validFor"), ensure_ascii=False) if body.get("validFor") else None,
                # Provider sets quoteDate
                "quote_date": fields.Datetime.now(),
            }

            q = request.env["tmf.quote"].sudo().create(vals)

            # Create quote items
            item_seq = 1
            for qi in body.get("quoteItem", []):
                request.env["tmf.quote.item"].sudo().create({
                    "quote_id": q.id,
                    "item_id": qi.get("id") or str(item_seq),
                    "action": qi.get("action"),
                    "quantity": qi.get("quantity") or 1,
                    "product_json": json.dumps(qi.get("product"), ensure_ascii=False) if qi.get("product") else None,
                    "product_offering_json": json.dumps(qi.get("productOffering"), ensure_ascii=False) if qi.get("productOffering") else None,
                    "attachment_json": json.dumps(qi.get("attachment", []), ensure_ascii=False),
                    "note_json": json.dumps(qi.get("note", []), ensure_ascii=False),
                    "related_party_json": json.dumps(qi.get("relatedParty", []), ensure_ascii=False),
                    "appointment_json": json.dumps(qi.get("appointment", []), ensure_ascii=False),
                    "quote_item_rel_json": json.dumps(qi.get("quoteItemRelationship", []), ensure_ascii=False),
                    "embedded_quote_item_json": json.dumps(qi.get("quoteItem", []), ensure_ascii=False),
                })
                item_seq += 1

            # Response codes:
            # - If resource created: 201
            # - If instantSyncQuote true: many CTKs accept 201 too, but keep your behavior if needed
            status = 200 if instant_sync else 201
            headers = [("Location", f"{BASE_PATH}/{q.tmf_id or q.id}")]
            return _json_response(q.to_tmf_json(), status=status, headers=headers)

        except Exception as e:
            # Ensure CTK gets JSON, not Odoo HTML error page
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return _error(500, "Internal error creating quote", details=str(e))

    @http.route(f"{BASE_PATH}/<string:quote_id>", methods=["PATCH"], type="http", auth="public", csrf=False)
    def patch_quote(self, quote_id, **kwargs):
        try:
            body = _parse_json_body()
            if body is None:
                return _error(400, "Invalid JSON")

            q = request.env["tmf.quote"].sudo().search([("tmf_id", "=", quote_id)], limit=1)
            if not q:
                return _error(404, "Quote not found")

            writable = {
                "category": "category",
                "description": "description",
                "externalId": "tmf_external_id",
                "state": "state",
                "version": "version",
                "agreement": "agreement_json",
                "billingAccount": "billing_account_json",
                "contactMedium": "contact_medium_json",
                "note": "note_json",
                "relatedParty": "related_party_json",
                "productOfferingQualification": "poq_json",
                "authorization": "authorization_json",
                "quoteTotalPrice": "quote_total_price_json",
                "validFor": "valid_for_json",
                "requestedQuoteCompletionDate": "requested_quote_completion_date",
                "expectedFulfillmentStartDate": "expected_fulfillment_start_date",
            }

            vals = {}
            for k, f in writable.items():
                if k not in body:
                    continue

                if f in ("requested_quote_completion_date", "expected_fulfillment_start_date"):
                    vals[f] = _parse_dt(body.get(k))
                elif f.endswith("_json") or f == "valid_for_json":
                    vals[f] = json.dumps(body.get(k), ensure_ascii=False)
                else:
                    vals[f] = body.get(k)

            if vals:
                q.write(vals)

            return _json_response(q.to_tmf_json(fields_param=_fields_param()), status=200)

        except Exception as e:
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return _error(500, "Internal error patching quote", details=str(e))

    @http.route(f"{BASE_PATH}/<string:quote_id>", methods=["DELETE"], type="http", auth="public", csrf=False)
    def delete_quote(self, quote_id, **kwargs):
        try:
            q = request.env["tmf.quote"].sudo().search([("tmf_id", "=", quote_id)], limit=1)
            if not q:
                return _error(404, "Quote not found")
            q.unlink()
            return _empty(status=204)
        except Exception as e:
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return _error(500, "Internal error deleting quote", details=str(e))

    # -------------------------
    # Hub registration (TMF pub/sub)
    # -------------------------
    @http.route(HUB_PATH, methods=["POST"], type="http", auth="public", csrf=False)
    def register_hub(self, **kwargs):
        try:
            body = _parse_json_body()
            if body is None or not body.get("callback"):
                return _error(400, "callback is mandatory")

            hub = request.env["tmf.hub.subscription"].sudo().create({
                "tmf_id": str(uuid.uuid4()),
                "callback": body.get("callback"),
                "query": body.get("query"),
                "topic": "TMF648Quote",
                "api_base": API_BASE,
            })

            headers = [("Location", f"{HUB_PATH}/{hub.tmf_id}")]
            return _json_response({"id": hub.tmf_id, "callback": hub.callback, "query": hub.query}, status=201, headers=headers)

        except Exception as e:
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return _error(500, "Internal error registering hub", details=str(e))

    @http.route(f"{HUB_PATH}/<string:hub_id>", methods=["DELETE"], type="http", auth="public", csrf=False)
    def unregister_hub(self, hub_id, **kwargs):
        try:
            hub = request.env["tmf.hub.subscription"].sudo().search([("tmf_id", "=", hub_id)], limit=1)
            if not hub:
                return _error(404, "Hub not found")
            hub.unlink()
            return _empty(status=204)
        except Exception as e:
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return _error(500, "Internal error unregistering hub", details=str(e))
