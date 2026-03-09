# -*- coding: utf-8 -*-
import json
import requests

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

API_BASE = "/tmf-api/paymentMethod/v4"
RESOURCE = "paymentMethod"
BASE_PATH = f"{API_BASE}/{RESOURCE}"
HUB_PATH = f"{API_BASE}/hub"


# -------- helpers --------
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


def _get_header(name):
    return request.httprequest.headers.get(name)


def _filter_domain_from_params(args):
    """
    Very small subset of filtering:
      ?status=Active&@type=BankCard&name=Main
    """
    domain = []
    if args.get("status"):
        domain.append(("status", "=", args.get("status")))
    if args.get("name"):
        domain.append(("name", "ilike", args.get("name")))
    if args.get("@type"):
        domain.append(("tmf_type", "=", args.get("@type")))
    if args.get("isPreferred") is not None:
        v = args.get("isPreferred")
        if isinstance(v, str):
            v = v.lower() in ("true", "1", "yes")
        domain.append(("is_preferred", "=", bool(v)))
    return domain


def _apply_fields_selection(obj, fields_param):
    """
    TMF supports ?fields=a,b,c for first-level fields. :contentReference[oaicite:10]{index=10}
    We implement simple projection on the produced TMF dict.
    """
    if not fields_param:
        return obj
    wanted = [f.strip() for f in fields_param.split(",") if f.strip()]
    if not wanted:
        return obj
    return {k: v for k, v in obj.items() if k in wanted or k.startswith("@") or k in ("id", "href")}


def _publish_event(event_type, payment_method_dict):
    """
    Send TMF event payload to every hub subscription in tmf_base (tmf.hub.subscription).
    The spec shows event envelope structure. :contentReference[oaicite:11]{index=11}
    """
    Hub = request.env["tmf.hub.subscription"].sudo()
    hubs = Hub.search([("api_name", "=", "TMF670")])
    if not hubs:
        return

    envelope = {
        "eventId": payment_method_dict.get("id"),
        "eventTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    # simpler: just use now iso
    from datetime import datetime, timezone
    envelope["eventTime"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    envelope["eventType"] = event_type
    envelope["event"] = {"paymentMethod": payment_method_dict}

    for hub in hubs:
        cb = hub.callback
        if not cb:
            continue
        try:
            requests.post(cb, json=envelope, timeout=3)
        except Exception:
            # best-effort only
            continue


# -------- controllers --------
class TMF670PaymentMethodController(http.Controller):

    # LIST
    @http.route(BASE_PATH, methods=["GET"], type="http", auth="public", csrf=False)
    def list_payment_methods(self, **kwargs):
        try:
            fields_param = kwargs.get("fields")
            limit = int(kwargs.get("limit", 100))
            offset = int(kwargs.get("offset", 0))

            domain = _filter_domain_from_params(kwargs)
            env = request.env["tmf.payment.method"].sudo()
            recs = env.search(domain, limit=limit, offset=offset, order="create_date desc")
            total = env.search_count(domain)

            out = []
            for r in recs:
                d = r.to_tmf_dict()
                d = _apply_fields_selection(d, fields_param)
                out.append(d)
            return _json_response(out, status=200, headers=[
                ("X-Total-Count", str(total)),
                ("X-Result-Count", str(len(out))),
            ])
        except Exception as e:
            return _error(500, "Internal error", details=str(e))

    # RETRIEVE
    @http.route(f"{BASE_PATH}/<string:tmf_id>", methods=["GET"], type="http", auth="public", csrf=False)
    def get_payment_method(self, tmf_id, **kwargs):
        try:
            fields_param = kwargs.get("fields")
            rec = request.env["tmf.payment.method"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
            if not rec:
                return _error(404, "Not found")

            d = rec.to_tmf_dict()
            d = _apply_fields_selection(d, fields_param)
            return _json_response(d, status=200)
        except Exception as e:
            return _error(500, "Internal error", details=str(e))

    # CREATE
    @http.route(BASE_PATH, methods=["POST"], type="http", auth="public", csrf=False)
    def create_payment_method(self, **kwargs):
        payload = _parse_json_body()
        if payload is None:
            return _error(400, "Invalid JSON body")

        try:
            rec = request.env["tmf.payment.method"].sudo().tmf_create_from_payload(payload, API_BASE)
            out = rec.to_tmf_dict()
            _publish_event("PaymentMethodCreateEvent", out)
            return _json_response(out, status=201)
        except ValidationError as ve:
            return _error(400, str(ve))
        except Exception as e:
            return _error(500, "Internal error", details=str(e))

    # PATCH (merge-patch or json-patch)
    @http.route(f"{BASE_PATH}/<string:tmf_id>", methods=["PATCH"], type="http", auth="public", csrf=False)
    def patch_payment_method(self, tmf_id, **kwargs):
        content_type = (_get_header("Content-Type") or "").lower()
        body = _parse_json_body()
        if body is None:
            return _error(400, "Invalid JSON body")

        try:
            rec = request.env["tmf.payment.method"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
            if not rec:
                return _error(404, "Not found")

            before = rec.to_tmf_dict()

            if "json-patch" in content_type:
                rec.tmf_apply_json_patch(body)
            else:
                # treat as merge patch (application/merge-patch+json or generic json)
                if not isinstance(body, dict):
                    return _error(400, "Merge patch body must be a JSON object")
                rec.tmf_apply_merge_patch(body)

            after = rec.to_tmf_dict()

            # notifications: status change vs attribute change
            if before.get("status") != after.get("status"):
                _publish_event("PaymentMethodStatusChangeEvent", after)
            else:
                _publish_event("PaymentMethodAttributeValueChangeEvent", after)

            return _json_response(after, status=200)

        except ValidationError as ve:
            return _error(400, str(ve))
        except Exception as e:
            return _error(500, "Internal error", details=str(e))

    # DELETE
    @http.route(f"{BASE_PATH}/<string:tmf_id>", methods=["DELETE"], type="http", auth="public", csrf=False)
    def delete_payment_method(self, tmf_id, **kwargs):
        try:
            rec = request.env["tmf.payment.method"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
            if not rec:
                return _error(404, "Not found")

            payload = rec.to_tmf_dict()
            rec.unlink()
            _publish_event("PaymentMethodDeleteEvent", payload)
            return request.make_response("", status=204)
        except Exception as e:
            return _error(500, "Internal error", details=str(e))


class TMF670HubController(http.Controller):
    """
    Hub endpoints in the TMF670 doc: POST /hub, DELETE /hub/{id}. :contentReference[oaicite:12]{index=12}
    We store hubs in tmf_base model tmf.hub.subscription with api_name='TMF670'.
    """

    @http.route(HUB_PATH, methods=["POST"], type="http", auth="public", csrf=False)
    def register_listener(self, **kwargs):
        payload = _parse_json_body()
        if payload is None:
            return _error(400, "Invalid JSON body")
        cb = payload.get("callback")
        query = payload.get("query")
        if not cb:
            return _error(400, "Missing 'callback'")

        try:
            Hub = request.env["tmf.hub.subscription"].sudo()
            rec = Hub.create({
                "api_name": "TMF670",
                "callback": cb,
                "query": query,
            })
            # spec example returns 201 + Location header. :contentReference[oaicite:13]{index=13}
            headers = [("Location", f"{HUB_PATH}/{rec.id}")]
            return _json_response({"id": str(rec.id), "callback": cb, "query": query}, status=201, headers=headers)
        except Exception as e:
            return _error(500, "Internal error", details=str(e))

    @http.route(f"{HUB_PATH}/<int:hub_id>", methods=["DELETE"], type="http", auth="public", csrf=False)
    def unregister_listener(self, hub_id, **kwargs):
        try:
            Hub = request.env["tmf.hub.subscription"].sudo()
            rec = Hub.search([("id", "=", hub_id), ("api_name", "=", "TMF670")], limit=1)
            if not rec:
                return _error(404, "Not found")
            rec.unlink()
            return request.make_response("", status=204)
        except Exception as e:
            return _error(500, "Internal error", details=str(e))
