# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import uuid
import json

API_BASE = "/tmf-api/recommendationManagement/v4"


class TMFRecommendationController(http.Controller):

    # ----------------------------------------------------------
    # POST /queryProductRecommendation
    # ----------------------------------------------------------
    @http.route(
        f"{API_BASE}/queryProductRecommendation",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def create_query_product_recommendation(self, **kwargs):
        # Parse body as JSON
        raw = request.httprequest.data or b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return request.make_json_response({"error": "Invalid JSON body"}, status=400)

        # TMF680 POST rule: at least one of these must be present :contentReference[oaicite:1]{index=1}
        mandatory_group = [
            "shoppingCart",
            "shoppingCartItem",
            "productOrder",
            "productOrderItem",
            "category",
            "relatedParty",
            "place",
        ]
        if not any(payload.get(k) for k in mandatory_group):
            return request.make_json_response(
                {"error": "At least one of shoppingCart/shoppingCartItem/productOrder/productOrderItem/category/relatedParty/place is mandatory"},
                status=400,
            )

        rec = request.env["tmf.query.product.recommendation"].sudo().create({
            "tmf_id": payload.get("id") or str(uuid.uuid4()),
            "tmf_type": payload.get("@type") or "QueryProductRecommendation",
            "base_type": payload.get("@baseType"),
            "schema_location": payload.get("@schemaLocation"),
            "shopping_cart": payload.get("shoppingCart"),
            "shopping_cart_item": payload.get("shoppingCartItem"),
            "product_order": payload.get("productOrder"),
            "product_order_item": payload.get("productOrderItem"),
            "category": payload.get("category"),
            "related_party": payload.get("relatedParty"),
            "place": payload.get("place"),
        })

        host = request.httprequest.host_url.rstrip("/")
        rec.href = f"{host}{API_BASE}/queryProductRecommendation/{rec.tmf_id}"

        # IMPORTANT for CTK: recommendationItem must be present and an array
        # (even if empty) because your CTK assertion expects an array.
        out = rec._to_tmf_json(host)
        out["recommendationItem"] = out.get("recommendationItem") or []

        # Return 200 to match your CTK run expectation (TMF680 allows 200/201) :contentReference[oaicite:2]{index=2}
        return request.make_json_response(out, status=200)

    # ----------------------------------------------------------
    # GET /queryProductRecommendation/{id}
    # ----------------------------------------------------------
    @http.route(
        f"{API_BASE}/queryProductRecommendation/<string:tmf_id>",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
    )
    def get_query_product_recommendation(self, tmf_id, **params):

        rec = request.env["tmf.query.product.recommendation"].sudo().search(
            [("tmf_id", "=", tmf_id)],
            limit=1,
        )

        if not rec:
            return request.make_json_response({}, status=404)

        return request.make_json_response(
            rec._to_tmf_json(request.httprequest.host_url.rstrip("/")),
            status=200,
        )
