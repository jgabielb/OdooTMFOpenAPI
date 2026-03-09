from odoo import http
from odoo.http import request
import json
import uuid
import traceback

API_BASE = "/tmf-api/shoppingCartManagement/v5"
RESOURCE = "shoppingCart"
BASE_PATH = f"{API_BASE}/{RESOURCE}"


def _json_response(payload, status=200, headers=None):
    hdrs = [("Content-Type", "application/json")]
    if headers:
        hdrs.extend(headers)
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=hdrs,
        status=status,
    )


def _parse_body():
    raw = request.httprequest.data or b"{}"
    return json.loads(raw.decode("utf-8"))


def _apply_fields_filter(obj, fields_param):
    """
    TMF 'fields' query param: return only selected attributes.
    CTK uses fields=@type.
    """
    if not fields_param:
        return obj

    wanted = [f.strip() for f in str(fields_param).split(",") if f.strip()]
    if not wanted:
        return obj

    # STRICT: only requested keys
    return {k: obj.get(k) for k in wanted if k in obj}


def _tmf_error(status_code, reason, code=None, trace=None):
    payload = {
        "@type": "Error",
        "status": str(status_code),
        "reason": reason,
    }
    if code:
        payload["code"] = code
    if trace:
        payload["trace"] = trace
    return payload


def _create_product_ref_or_value(prod_dict):
    """
    Create a tmf.product.ref.or.value record from TMF ProductRefOrValue payload.
    Returns record id or False.
    """
    href_val = prod_dict.get("href")
    if not isinstance(href_val, str):
        return False

    # schema expects an object if 'product' exists; but 'id' might be absent in some CTK payloads
    # We'll still create if any meaningful fields are present.
    any_data = any(prod_dict.get(k) for k in ("id", "href", "name", "@type", "@referredType"))
    if not any_data:
        return False

    return request.env["tmf.product.ref.or.value"].sudo().create({
        "tmf_id": prod_dict.get("id"),
        "href": prod_dict.get("href"),
        "name": prod_dict.get("name"),
        "referred_type": prod_dict.get("@referredType") or "Product",
        "tmf_type": prod_dict.get("@type") or "ProductRefOrValue",
        # optional embedded json if you use it
        "product_json": json.dumps(prod_dict, ensure_ascii=False),
    }).id


def _create_product_offering_ref(po_dict):
    """
    Create a tmf.product.offering.ref record from TMF ProductOfferingRef payload.
    Returns record id or False.
    """
    if not isinstance(po_dict, dict):
        return False

    any_data = any(po_dict.get(k) for k in ("id", "href", "name", "@type", "@referredType"))
    if not any_data:
        return False

    return request.env["tmf.product.offering.ref"].sudo().create({
        "tmf_id": po_dict.get("id") or str(uuid.uuid4()),
        "href": po_dict.get("href"),
        "name": po_dict.get("name"),
        "referred_type": po_dict.get("@referredType") or "ProductOffering",
        "tmf_type": po_dict.get("@type") or "ProductOfferingRef",
        "tmf_base_type": po_dict.get("@baseType"),
        "tmf_schema_location": po_dict.get("@schemaLocation"),
    }).id


def _resolve_partner_from_related_party(related_party):
    parties = related_party if isinstance(related_party, list) else []
    Partner = request.env["res.partner"].sudo()
    for party in parties:
        if not isinstance(party, dict):
            continue
        pid = party.get("id")
        pname = party.get("name")
        if pid:
            partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
            if not partner and str(pid).isdigit():
                partner = Partner.browse(int(pid))
            if partner and partner.exists():
                return partner.id
        if pname:
            partner = Partner.search([("name", "=", pname)], limit=1)
            if partner:
                return partner.id
    return False


class TMFShoppingCartController(http.Controller):

    @http.route(BASE_PATH, type="http", auth="public", methods=["GET"], csrf=False)
    def list_carts(self, **params):
        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        domain = []
        env = request.env["tmf.shopping.cart"].sudo()
        recs = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)
        payload = [r.to_tmf_json() for r in recs]

        fields_param = params.get("fields")
        if fields_param:
            payload = [_apply_fields_filter(p, fields_param) for p in payload]

        return _json_response(payload, status=200, headers=[("X-Total-Count", str(total)), ("X-Result-Count", str(len(payload)))])

    @http.route(f"{BASE_PATH}/<string:cart_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_cart(self, cart_id, **params):
        rec = request.env["tmf.shopping.cart"].sudo().search([("tmf_id", "=", cart_id)], limit=1)
        if not rec:
            return _json_response(_tmf_error(404, "Not found", code="notFound"), status=404)

        payload = rec.to_tmf_json()
        fields_param = params.get("fields")
        if fields_param:
            payload = _apply_fields_filter(payload, fields_param)

        return _json_response(payload, status=200)

    @http.route(BASE_PATH, type="http", auth="public", methods=["POST"], csrf=False)
    def create_cart(self, **params):
        try:
            payload = _parse_body() or {}

            # CTK-proof defaults
            if not payload.get("@type"):
                payload["@type"] = "ShoppingCart"

            env = request.env["tmf.shopping.cart"].sudo()

            # Validate: must NOT require cartItem
            env.new({}).validate_tmf_create(payload)

            cart = env.create({
                "tmf_id": str(uuid.uuid4()),
                "tmf_type": "ShoppingCart",
                # keep these optional; avoid type problems
                "tmf_base_type": payload.get("@baseType") or False,
                "tmf_schema_location": payload.get("@schemaLocation") or False,
                "partner_id": _resolve_partner_from_related_party(payload.get("relatedParty")),
            })

            # cartItem optional
            for i in (payload.get("cartItem") or []):
                # productOffering/product mapping (so schema sees objects, not null/string)
                po_id = _create_product_offering_ref(i.get("productOffering"))
                prod_id = _create_product_ref_or_value(i.get("product"))

                request.env["tmf.shopping.cart.item"].sudo().create({
                    "cart_id": cart.id,
                    "item_id": i.get("id") or str(uuid.uuid4()),
                    "tmf_type": i.get("@type") or "CartItem",
                    "action": i.get("action") or "add",
                    "quantity": i.get("quantity") or 1,
                    "status": i.get("status") or "active",
                    "product_offering_id": po_id or False,
                    "product_id": prod_id or False,
                })

            return _json_response(cart.to_tmf_json(), status=201)

        except Exception as e:
            request.env.cr.rollback()
            return _json_response(
                _tmf_error(400, str(e), code="invalidRequest", trace=traceback.format_exc()),
                status=400
            )

    @http.route(f"{BASE_PATH}/<string:cart_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_cart(self, cart_id, **params):
        rec = request.env["tmf.shopping.cart"].sudo().search([("tmf_id", "=", cart_id)], limit=1)
        if not rec:
            return _json_response(_tmf_error(404, "Not found", code="notFound"), status=404)
        rec.unlink()
        return _json_response({}, status=204)

    @http.route(f"{BASE_PATH}/<string:cart_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_cart(self, cart_id, **params):
        return _json_response(_tmf_error(501, "Not implemented", code="notImplemented"), status=501)
