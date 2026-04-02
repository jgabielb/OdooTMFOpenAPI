"""TMF637 Product Inventory controllers.

Phase 1C1: Align controller plumbing with tmf_base.TMFBaseController:
- JSON parsing
- error responses
- id normalization
- pagination helpers

Business mapping remains unchanged.
"""

# -*- coding: utf-8 -*-

import json
from datetime import datetime, timezone

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController


API_BASE = "/tmf-api/productInventoryManagement/v5"
RESOURCE = "product"
BASE_PATH = f"{API_BASE}/{RESOURCE}"


def _apply_fields_filter(obj: dict, fields_param):
    if not fields_param:
        return obj
    wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
    if not wanted:
        return obj
    # Always keep mandatory identifiers for CTK
    keep = wanted.union({"id", "href", "@type"})
    return {k: v for k, v in obj.items() if k in keep}


def _as_iso_string(v):
    # v can be datetime, string, False/None
    if not v:
        return None
    if isinstance(v, str):
        return v
    try:
        return v.isoformat()
    except Exception:
        return str(v)


def _ensure_id(rec):
    """
    CTK needs id in response.
    If client didn't send id, generate a deterministic-ish one using internal id.
    """
    if not getattr(rec, "tmf_id", None):
        rec.write({"tmf_id": str(rec.id)})
    return rec.tmf_id


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_product_response(rec, data: dict):
    data = data or {}

    # mandatory
    data["@type"] = "Product"

    # id/href
    data["id"] = data.get("id") or _ensure_id(rec)
    data["href"] = f"{BASE_PATH}/{data['id']}"

    # creationDate as string (required by CTK schema if present in payload)
    creation_val = data.get("creationDate") or getattr(rec, "creation_date", None)
    data["creationDate"] = _as_iso_string(creation_val) or _now_iso()

    # ---- orderDate: ONLY include if it is a real string ----
    order_val = data.get("orderDate") or getattr(rec, "order_date", None)
    order_str = _as_iso_string(order_val)

    if order_str:
        data["orderDate"] = order_str
    else:
        # If it exists but is not a string/null, remove it (schema complains if present & not string)
        data.pop("orderDate", None)

    # Optional: same approach for other optional date fields
    start_val = data.get("startDate") or getattr(rec, "start_date", None)
    start_str = _as_iso_string(start_val)
    if start_str:
        data["startDate"] = start_str
    else:
        data.pop("startDate", None)

    term_val = data.get("terminationDate") or getattr(rec, "termination_date", None)
    term_str = _as_iso_string(term_val)
    if term_str:
        data["terminationDate"] = term_str
    else:
        data.pop("terminationDate", None)

    # ---- productSpecification: must be object if present ----
    ps = data.get("productSpecification")

    # Recover from model JSON field if available
    if not isinstance(ps, dict):
        model_ps = getattr(rec, "product_specification_json", None)
        if isinstance(model_ps, dict):
            ps = model_ps

    if isinstance(ps, dict):
        # Ensure minimal ref-like object
        ps.setdefault("@type", "ProductSpecificationRef")
        ps.setdefault("id", "spec-1")
        ps.setdefault("href", "/tmf-api/productCatalogManagement/v5/productSpecification/spec-1")
        data["productSpecification"] = ps
    else:
        # Remove invalid value (None/list/string/bool)
        data.pop("productSpecification", None)

    # ---- arrays: must be array if present ----
    for k in ("relatedParty", "place", "productCharacteristic", "realizingService"):
        v = data.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            continue

        model_map = {
            "relatedParty": "related_party_json",
            "place": "place_json",
            "productCharacteristic": "product_characteristic_json",
            "realizingService": "realizing_service_json",
        }
        mv = getattr(rec, model_map.get(k, ""), None)
        if isinstance(mv, list):
            data[k] = mv
        else:
            data.pop(k, None)

    # TMF637 CTK expects each productCharacteristic item to declare @type.
    chars = data.get("productCharacteristic")
    if isinstance(chars, list):
        normalized_chars = []
        for item in chars:
            if isinstance(item, dict):
                one = dict(item)
                one.setdefault("@type", "StringCharacteristic")
                normalized_chars.append(one)
            else:
                normalized_chars.append(item)
        data["productCharacteristic"] = normalized_chars

    parties = data.get("relatedParty")
    if isinstance(parties, list):
        normalized_parties = []
        for item in parties:
            if isinstance(item, dict):
                one = dict(item)
                one.setdefault("@type", "RelatedPartyRefOrPartyRoleRef")
                normalized_parties.append(one)
            else:
                normalized_parties.append(item)
        data["relatedParty"] = normalized_parties

    return data



class TMF637ProductInventoryController(TMFBaseController):

    # -------------------------
    # GET /product/{id}
    # -------------------------
    @http.route(
        f"{BASE_PATH}/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_product_by_id(self, tmf_id, **query):
        fields_param = query.get("fields")
        Product = request.env["tmf.product"].sudo()

        tmf_id = self._normalize_tmf_id(tmf_id)

        rec = Product.search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec and tmf_id.isdigit():
            rec = Product.browse(int(tmf_id))
        if not rec or not rec.exists():
            return self._error(404, "NotFound", f"Product '{tmf_id}' not found")

        data = _normalize_product_response(rec, rec.to_tmf_json())
        return self._json(_apply_fields_filter(data, fields_param), status=200)

    # -------------------------
    # GET /product
    # -------------------------
    @http.route(
        f"{BASE_PATH}",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_products(self, **query):
        fields_param = query.get("fields")
        Product = request.env["tmf.product"].sudo()

        domain = []
        # filters
        if "status" in query:
            domain.append(("status", "=", query["status"]))
        if "isCustomerVisible" in query:
            val = str(query["isCustomerVisible"]).lower() in ("true", "1", "yes")
            domain.append(("is_customer_visible", "=", val))
        if "isBundle" in query:
            val = str(query["isBundle"]).lower() in ("true", "1", "yes")
            domain.append(("is_bundle", "=", val))

        limit, offset = self._paginate_params(query)

        recs = Product.search(domain, limit=limit, offset=offset, order="id asc")
        total = Product.search_count(domain)
        out = []
        for r in recs:
            data = _normalize_product_response(r, r.to_tmf_json())
            out.append(_apply_fields_filter(data, fields_param))

        return self._json(
            out,
            status=200,
            headers=[
                ("X-Total-Count", str(total)),
                ("X-Result-Count", str(len(out))),
            ],
        )

    # -------------------------
    # POST /product
    # -------------------------
    @http.route(
        f"{BASE_PATH}",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_product(self, **query):
        payload = self._parse_json_body()
        if not isinstance(payload, dict):
            return self._error(400, "InvalidRequest", "Invalid JSON payload")

        Product = request.env["tmf.product"].sudo()
        vals = self._tmf_to_odoo_vals(payload)
        rec = Product.create(vals)

        # Ensure id exists
        _ensure_id(rec)

        data = _normalize_product_response(rec, rec.to_tmf_json())
        return self._json(data, status=201)

    # -------------------------
    # PATCH /product/{id}
    # -------------------------
    @http.route(
        f"{BASE_PATH}/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["PATCH"],
        csrf=False,
    )
    def patch_product(self, tmf_id, **query):
        tmf_id = self._normalize_tmf_id(tmf_id)

        payload = self._parse_json_body()
        if not isinstance(payload, dict):
            return self._error(400, "InvalidRequest", "Invalid JSON payload")

        Product = request.env["tmf.product"].sudo()
        rec = Product.search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec and tmf_id.isdigit():
            rec = Product.browse(int(tmf_id))
        if not rec or not rec.exists():
            return self._error(404, "NotFound", f"Product '{tmf_id}' not found")

        vals = self._tmf_to_odoo_vals(payload, partial=True)
        if vals:
            rec.write(vals)

        _ensure_id(rec)

        data = _normalize_product_response(rec, rec.to_tmf_json())
        return self._json(data, status=200)

    # -------------------------
    # DELETE /product/{id}
    # -------------------------
    @http.route(
        f"{BASE_PATH}/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def delete_product(self, tmf_id, **query):
        Product = request.env["tmf.product"].sudo()

        tmf_id = self._normalize_tmf_id(tmf_id)
        rec = Product.search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec and tmf_id.isdigit():
            rec = Product.browse(int(tmf_id))
        if not rec or not rec.exists():
            return self._error(404, "NotFound", f"Product '{tmf_id}' not found")

        rec.unlink()
        return request.make_response("", status=204)

    # -------------------------
    # Helpers
    # -------------------------
    def _tmf_to_odoo_vals(self, payload: dict, partial: bool = False) -> dict:
        """
        Minimal mapping for TMF637 Product.
        """
        vals = {}

        # External TMF id
        if "id" in payload:
            vals["tmf_id"] = payload.get("id")

        if "name" in payload:
            vals["name"] = payload.get("name") or ""

        if "description" in payload:
            vals["description"] = payload.get("description") or ""

        if "isBundle" in payload:
            vals["is_bundle"] = bool(payload.get("isBundle"))

        if "isCustomerVisible" in payload:
            vals["is_customer_visible"] = bool(payload.get("isCustomerVisible"))

        # Dates: keep as-is if your model expects string; otherwise you can parse to datetime
        if "creationDate" in payload:
            vals["creation_date"] = payload.get("creationDate")

        if "orderDate" in payload:
            vals["order_date"] = payload.get("orderDate")

        if "startDate" in payload:
            vals["start_date"] = payload.get("startDate")

        if "terminationDate" in payload:
            vals["termination_date"] = payload.get("terminationDate")

        if "status" in payload:
            vals["status"] = payload.get("status")

        # Nested structures as JSON if present in your tmf.product
        ProductModel = request.env["tmf.product"]
        if "productCharacteristic" in payload and hasattr(ProductModel, "product_characteristic_json"):
            vals["product_characteristic_json"] = payload.get("productCharacteristic") or []

        if "relatedParty" in payload and hasattr(ProductModel, "related_party_json"):
            vals["related_party_json"] = payload.get("relatedParty") or []

        if "place" in payload and hasattr(ProductModel, "place_json"):
            vals["place_json"] = payload.get("place") or []

        if partial:
            return vals

        vals.setdefault("is_bundle", False)
        vals.setdefault("is_customer_visible", False)
        return vals
