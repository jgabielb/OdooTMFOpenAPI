import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/stock/v4"


def _json_response(payload, status=200, headers=None):
    base_headers = [("Content-Type", "application/json")]
    if headers:
        base_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=base_headers, status=status)


def _error(status, reason):
    return _json_response({"error": {"status": status, "reason": reason}}, status=status)


def _parse_json():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _fields_filter(payload, fields_csv):
    if not fields_csv:
        return payload
    wanted = {x.strip() for x in str(fields_csv).split(",") if x.strip()}
    if not wanted:
        return payload
    mandatory = {"id", "href"}
    wanted |= mandatory
    return {k: v for k, v in payload.items() if k in wanted}


def _find_by_rid(model_name, rid):
    model = request.env[model_name].sudo()
    rec = model.search([("tmf_id", "=", rid)], limit=1)
    if rec:
        return rec
    if str(rid).isdigit():
        rec = model.browse(int(rid))
        if rec.exists():
            return rec
    return None


class TMF687StockController(http.Controller):
    @http.route(f"{API_BASE}/productStock", type="http", auth="public", methods=["GET"], csrf=False)
    def list_product_stock(self, **params):
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.product.stock"].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(r.to_tmf_json(), params.get("fields")) for r in recs]
        return _json_response(payload, status=200, headers=[("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))])

    @http.route(f"{API_BASE}/productStock/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_product_stock(self, rid, **params):
        rec = _find_by_rid("tmf.product.stock", rid)
        if not rec:
            return _error(404, f"ProductStock {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/productStock", type="http", auth="public", methods=["POST"], csrf=False)
    def create_product_stock(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        missing = [k for k in ("productStockStatusType", "productStockLevel", "stockedProduct") if k not in data]
        if missing:
            return _error(400, f"Missing mandatory attribute(s): {', '.join(missing)}")
        vals = {
            "name": data.get("name"),
            "description": data.get("description"),
            "product_stock_status_type": data.get("productStockStatusType"),
            "product_stock_level": data.get("productStockLevel") or {},
            "stocked_product": data.get("stockedProduct") or {},
            "extra_json": {k: v for k, v in data.items() if k not in {"name", "description", "productStockStatusType", "productStockLevel", "stockedProduct", "id", "href"}},
        }
        rec = request.env["tmf.product.stock"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/productStock/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_product_stock(self, rid, **_params):
        rec = _find_by_rid("tmf.product.stock", rid)
        if not rec:
            return _error(404, f"ProductStock {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        vals = {}
        if "name" in patch:
            vals["name"] = patch.get("name")
        if "description" in patch:
            vals["description"] = patch.get("description")
        if "productStockStatusType" in patch:
            vals["product_stock_status_type"] = patch.get("productStockStatusType")
        if "productStockLevel" in patch:
            vals["product_stock_level"] = patch.get("productStockLevel") or {}
        if "stockedProduct" in patch:
            vals["stocked_product"] = patch.get("stockedProduct") or {}
        extra = rec.extra_json.copy() if isinstance(rec.extra_json, dict) else {}
        for k, v in patch.items():
            if k not in {"name", "description", "productStockStatusType", "productStockLevel", "stockedProduct", "id", "href"}:
                extra[k] = v
        vals["extra_json"] = extra
        rec.sudo().write(vals)
        return _json_response(rec.to_tmf_json(), status=200)

    @http.route(f"{API_BASE}/reserveProductStock", type="http", auth="public", methods=["GET"], csrf=False)
    def list_reserve_product_stock(self, **params):
        domain = []
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.reserve.product.stock"].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(r.to_tmf_json(), params.get("fields")) for r in recs]
        return _json_response(payload, status=200, headers=[("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))])

    @http.route(f"{API_BASE}/reserveProductStock/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_reserve_product_stock(self, rid, **params):
        rec = _find_by_rid("tmf.reserve.product.stock", rid)
        if not rec:
            return _error(404, f"ReserveProductStock {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/reserveProductStock", type="http", auth="public", methods=["POST"], csrf=False)
    def create_reserve_product_stock(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        if "reserveProductStockItem" not in data:
            return _error(400, "Missing mandatory attribute: reserveProductStockItem")
        vals = {
            "reserve_product_stock_item": data.get("reserveProductStockItem") or [],
            "reserve_product_stock_state": data.get("reserveProductStockState") or "accepted",
            "extra_json": {k: v for k, v in data.items() if k not in {"reserveProductStockItem", "reserveProductStockState", "id", "href"}},
        }
        rec = request.env["tmf.reserve.product.stock"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/reserveProductStock/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_reserve_product_stock(self, rid, **_params):
        rec = _find_by_rid("tmf.reserve.product.stock", rid)
        if not rec:
            return _error(404, f"ReserveProductStock {rid} not found")
        patch = _parse_json()
        if not isinstance(patch, dict):
            return _error(400, "Invalid JSON body")
        vals = {}
        if "reserveProductStockItem" in patch:
            vals["reserve_product_stock_item"] = patch.get("reserveProductStockItem") or []
        if "reserveProductStockState" in patch:
            vals["reserve_product_stock_state"] = patch.get("reserveProductStockState") or rec.reserve_product_stock_state
        extra = rec.extra_json.copy() if isinstance(rec.extra_json, dict) else {}
        for k, v in patch.items():
            if k not in {"reserveProductStockItem", "reserveProductStockState", "id", "href"}:
                extra[k] = v
        vals["extra_json"] = extra
        rec.sudo().write(vals)
        return _json_response(rec.to_tmf_json(), status=200)
