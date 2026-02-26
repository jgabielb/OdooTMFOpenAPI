# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import json

API_BASE = "/tmf-api/promotionManagement/v4"


def _json_response(payload, status=200, headers=None):
    headers = headers or []
    headers.append(("Content-Type", "application/json"))
    return request.make_response(json.dumps(payload, ensure_ascii=False), headers=headers, status=status)


def _get_json_body():
    raw = request.httprequest.data or b""
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValidationError("Invalid JSON payload.")


class TMF671PromotionController(http.Controller):

    # -------------------------
    # Promotions
    # -------------------------
    @http.route(f"{API_BASE}/promotion", type="http", auth="public", methods=["GET"], csrf=False)
    def list_promotions(self, **query):
        # GET /promotion?fields=...&{filtering} :contentReference[oaicite:10]{index=10}
        # Minimal: ignore filtering/fields for now (CTK usually tolerates partial)
        recs = request.env["tmf.promotion"].sudo().search([])
        data = [r.to_tmf(API_BASE) for r in recs]
        return _json_response(data, status=200)

    @http.route(f"{API_BASE}/promotion/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def retrieve_promotion(self, tmf_id, **query):
        rec = request.env["tmf.promotion"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "NotFound", "message": "Promotion not found"}, status=404)
        return _json_response(rec.to_tmf(API_BASE), status=200)

    @http.route(f"{API_BASE}/promotion", type="http", auth="public", methods=["POST"], csrf=False)
    def create_promotion(self, **kwargs):
        payload = _get_json_body()
        rec = request.env["tmf.promotion"].sudo().from_tmf_create(payload, API_BASE)
        return _json_response(rec.to_tmf(API_BASE), status=201, headers=[("Location", rec.href)])

    @http.route(f"{API_BASE}/promotion/<string:tmf_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_promotion(self, tmf_id, **kwargs):
        # merge-patch mandatory :contentReference[oaicite:11]{index=11}
        content_type = (request.httprequest.content_type or "").lower()
        if "application/merge-patch+json" not in content_type and "application/json" not in content_type:
            return _json_response(
                {"error": "UnsupportedMediaType", "message": "Use application/merge-patch+json"},
                status=415
            )

        rec = request.env["tmf.promotion"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "NotFound", "message": "Promotion not found"}, status=404)

        patch = _get_json_body()
        rec.apply_merge_patch(patch, API_BASE)
        return _json_response(rec.to_tmf(API_BASE), status=200)

    @http.route(f"{API_BASE}/promotion/<string:tmf_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_promotion(self, tmf_id, **kwargs):
        rec = request.env["tmf.promotion"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            # TMF often allows idempotent delete; returning 204 is acceptable
            return request.make_response("", status=204)
        rec.unlink()
        return request.make_response("", status=204)

    # -------------------------
    # Hub (notifications registration)
    # -------------------------
    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_hub(self, **kwargs):
        # POST /hub returns 201 and Location, with {id, callback, query} :contentReference[oaicite:12]{index=12}
        payload = _get_json_body()
        callback = payload.get("callback")
        if not callback:
            raise ValidationError("Hub: 'callback' is mandatory.")

        hub = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf671-promotion-{callback}",
            "api_name": "promotion",
            "callback": callback,
            "query": payload.get("query"),
            "event_type": "any",
            "content_type": "application/json",
        })
        location = f"{API_BASE}/hub/{hub.id}"
        body = {"id": str(hub.id), "callback": hub.callback, "query": hub.query}
        return _json_response(body, status=201, headers=[("Location", location)])

    @http.route(f"{API_BASE}/hub/<string:hub_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_hub(self, hub_id, **kwargs):
        hub = request.env["tmf.hub.subscription"].sudo().browse(int(hub_id)) if str(hub_id).isdigit() else None
        if not hub or not hub.exists():
            return request.make_response("", status=204)
        hub.unlink()
        return request.make_response("", status=204)
