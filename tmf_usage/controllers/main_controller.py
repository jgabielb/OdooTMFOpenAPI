# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


def _json_response(payload, status=200, extra_headers=None):
    headers = [('Content-Type', 'application/json')]
    if extra_headers:
        headers.extend(extra_headers)
    return request.make_response(json.dumps(payload), headers=headers, status=status)


def _location(path):
    return [('Location', path)]


def _parse_body():
    raw = request.httprequest.data or b"{}"
    return json.loads(raw.decode("utf-8"))


def _only_fields(payload: dict, fields_csv: str | None):
    """TMF style: ?fields=id,href,... (applies to each object)."""
    if not fields_csv:
        return payload
    wanted = {f.strip() for f in fields_csv.split(",") if f.strip()}
    return {k: v for k, v in payload.items() if k in wanted}


def _camel_to_snake_map():
    # TMF -> Odoo fields
    return {
        "description": "description",
        "usageDate": "usage_date",
        "usageType": "usage_type",
        "status": "status",
        # nested:
        "usageSpecification": "usage_specification_id",
        "ratedProductUsage": "rated_product_usage_ids",
        "relatedParty": "related_party_ids",
        "usageCharacteristic": "usage_characteristic_ids",
    }


def _build_domain(model, params):
    # TMF standard params
    ignore = {"fields", "offset", "limit", "sort"}
    m = _camel_to_snake_map()
    domain = []

    # ✅ CTK uses: ?id=<uuid>
    if "id" in params:
        # In TMF resources, "id" maps to tmf_id
        if "tmf_id" in model._fields:
            domain.append(("tmf_id", "=", params["id"]))
        else:
            # fallback (rare): if no tmf_id field exists
            domain.append(("id", "=", params["id"]))
        return domain

    for k, v in params.items():
        if k in ignore:
            continue

        # Allow camelCase mapped filters
        if k in m and m[k] in model._fields:
            f = m[k]
            domain.append((f, "=", v))
            continue

        # Allow snake_case directly
        if k in model._fields:
            domain.append((k, "=", v))

    return domain


def _apply_sort(model, sort_csv):
    if not sort_csv:
        return None
    parts = [p.strip() for p in sort_csv.split(",") if p.strip()]
    order_parts = []
    for p in parts:
        direction = "asc"
        field = p
        if p.startswith("-"):
            direction = "desc"
            field = p[1:]
        f = _camel_to_snake_map().get(field, field)
        if f in model._fields:
            order_parts.append(f"{f} {direction}")
    return ", ".join(order_parts) if order_parts else None


def _find_by_rid(Model, rid: str):
    """Find by tmf_id first, then numeric id."""
    rec = Model.search([('tmf_id', '=', rid)], limit=1)
    if not rec and rid.isdigit():
        rec = Model.browse(int(rid))
    return rec


class TMFUsageController(http.Controller):

    @http.route('/tmf-api/usageManagement/v4/usage', type='http', auth='public', methods=['GET'], csrf=False)
    def usage_list(self, **params):
        Model = request.env['tmf.usage'].sudo()
        domain = _build_domain(Model, params)
        order = _apply_sort(Model, params.get("sort"))
        offset = int(params.get("offset", 0) or 0)
        limit = int(params.get("limit", 0) or 0) or None
        fields_csv = params.get("fields")

        recs = Model.search(domain, offset=offset, limit=limit, order=order)
        return _json_response([r.to_tmf_json(fields_csv=fields_csv) for r in recs])

    @http.route('/tmf-api/usageManagement/v4/usage/<string:rid>', type='http', auth='public', methods=['GET'], csrf=False)
    def usage_get(self, rid, **params):
        Model = request.env['tmf.usage'].sudo()

        # ✅ Fix: avoid precedence bug + empty browse()
        rec = _find_by_rid(Model, rid)
        if not rec or not rec.exists():
            return _json_response({"error": "Not found"}, status=404)

        return _json_response(rec.to_tmf_json(fields_csv=params.get("fields")))

    @http.route('/tmf-api/usageManagement/v4/usage', type='http', auth='public', methods=['POST'], csrf=False)
    def usage_create(self, **params):
        try:
            data = _parse_body()
            Model = request.env['tmf.usage'].sudo()

            vals = {}
            m = _camel_to_snake_map()

            for tmf_key in ["description", "usageDate", "usageType", "status"]:
                if tmf_key in data:
                    vals[m[tmf_key]] = data[tmf_key]

            # usageSpecification ref -> many2one
            if "usageSpecification" in data and isinstance(data["usageSpecification"], dict):
                sid = data["usageSpecification"].get("id")
                if sid:
                    spec = request.env["tmf.usage.specification"].sudo().search([("tmf_id", "=", sid)], limit=1)
                    if not spec and sid.isdigit():
                        spec = request.env["tmf.usage.specification"].sudo().browse(int(sid))
                    if spec and spec.exists():
                        vals["usage_specification_id"] = spec.id

            rec = Model.create(vals)

            # one2many: create nested records
            if isinstance(data.get("usageCharacteristic"), list):
                for ch in data["usageCharacteristic"]:
                    if isinstance(ch, dict) and ch.get("name"):
                        request.env["tmf.usage.characteristic"].sudo().create({
                            "usage_id": rec.id,
                            "name": ch.get("name"),
                            "value": ch.get("value"),
                            "value_type": ch.get("valueType"),
                        })

            if isinstance(data.get("relatedParty"), list):
                for p in data["relatedParty"]:
                    if isinstance(p, dict):
                        request.env["tmf.usage.related.party"].sudo().create({
                            "usage_id": rec.id,
                            "party_id": p.get("id"),
                            "href": p.get("href"),
                            "name": p.get("name"),
                            "role": p.get("role"),
                            "referred_type": p.get("@referredType"),
                        })

            if isinstance(data.get("ratedProductUsage"), list):
                for rpu in data["ratedProductUsage"]:
                    if isinstance(rpu, dict):
                        request.env["tmf.rated.product.usage"].sudo().create({
                            "usage_id": rec.id,
                            "usage_rating_tag": rpu.get("usageRatingTag"),
                            "rating_date": rpu.get("ratingDate"),
                            "is_billed": bool(rpu.get("isBilled")) if rpu.get("isBilled") is not None else False,
                            "tax_included_rating_amount": rpu.get("taxIncludedRatingAmount") or 0.0,
                            "tax_excluded_rating_amount": rpu.get("taxExcludedRatingAmount") or 0.0,
                            "currency_code": rpu.get("currencyCode"),
                        })

            tmf_id = rec.tmf_id or str(rec.id)
            loc = f"/tmf-api/usageManagement/v4/usage/{tmf_id}"
            return _json_response(rec.to_tmf_json(), status=201, extra_headers=_location(loc))
        except Exception as e:
            # ✅ still return JSON, not HTML
            return _json_response({"error": str(e)}, status=400)

    @http.route('/tmf-api/usageManagement/v4/usage/<string:rid>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def usage_patch(self, rid, **params):
        try:
            data = _parse_body()
            Model = request.env['tmf.usage'].sudo()

            rec = _find_by_rid(Model, rid)
            if not rec or not rec.exists():
                return _json_response({"error": "Not found"}, status=404)

            m = _camel_to_snake_map()
            vals = {}

            for tmf_key in ["description", "usageDate", "usageType", "status"]:
                if tmf_key in data:
                    vals[m[tmf_key]] = data[tmf_key]

            # usageSpecification patch
            if "usageSpecification" in data and isinstance(data["usageSpecification"], dict):
                sid = data["usageSpecification"].get("id")
                if sid:
                    spec = request.env["tmf.usage.specification"].sudo().search([("tmf_id", "=", sid)], limit=1)
                    if not spec and sid.isdigit():
                        spec = request.env["tmf.usage.specification"].sudo().browse(int(sid))
                    if spec and spec.exists():
                        vals["usage_specification_id"] = spec.id

            if vals:
                rec.write(vals)

            # Replace nested arrays if provided
            if "usageCharacteristic" in data and isinstance(data["usageCharacteristic"], list):
                rec.usage_characteristic_ids.unlink()
                for ch in data["usageCharacteristic"]:
                    if isinstance(ch, dict) and ch.get("name"):
                        request.env["tmf.usage.characteristic"].sudo().create({
                            "usage_id": rec.id,
                            "name": ch.get("name"),
                            "value": ch.get("value"),
                            "value_type": ch.get("valueType"),
                        })

            if "relatedParty" in data and isinstance(data["relatedParty"], list):
                rec.related_party_ids.unlink()
                for p in data["relatedParty"]:
                    if isinstance(p, dict):
                        request.env["tmf.usage.related.party"].sudo().create({
                            "usage_id": rec.id,
                            "party_id": p.get("id"),
                            "href": p.get("href"),
                            "name": p.get("name"),
                            "role": p.get("role"),
                            "referred_type": p.get("@referredType"),
                        })

            if "ratedProductUsage" in data and isinstance(data["ratedProductUsage"], list):
                rec.rated_product_usage_ids.unlink()
                for rpu in data["ratedProductUsage"]:
                    if isinstance(rpu, dict):
                        request.env["tmf.rated.product.usage"].sudo().create({
                            "usage_id": rec.id,
                            "usage_rating_tag": rpu.get("usageRatingTag"),
                            "rating_date": rpu.get("ratingDate"),
                            "is_billed": bool(rpu.get("isBilled")) if rpu.get("isBilled") is not None else False,
                            "tax_included_rating_amount": rpu.get("taxIncludedRatingAmount") or 0.0,
                            "tax_excluded_rating_amount": rpu.get("taxExcludedRatingAmount") or 0.0,
                            "currency_code": rpu.get("currencyCode"),
                        })

            return _json_response(rec.to_tmf_json(fields_csv=params.get("fields")))
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    @http.route('/tmf-api/usageManagement/v4/usage/<string:rid>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def usage_delete(self, rid, **params):
        Model = request.env['tmf.usage'].sudo()
        rec = _find_by_rid(Model, rid)
        if not rec or not rec.exists():
            return _json_response({"error": "Not found"}, status=404)
        rec.unlink()
        return _json_response({}, status=204)

    # Aliases (/Usage)
    @http.route('/tmf-api/usageManagement/v4/Usage', type='http', auth='public', methods=['GET'], csrf=False)
    def Usage_list_alias(self, **params):
        return self.usage_list(**params)

    @http.route('/tmf-api/usageManagement/v4/Usage', type='http', auth='public', methods=['POST'], csrf=False)
    def Usage_create_alias(self, **params):
        return self.usage_create(**params)

    @http.route('/tmf-api/usageManagement/v4/Usage/<string:rid>', type='http', auth='public', methods=['GET', 'PATCH', 'DELETE'], csrf=False)
    def Usage_item_alias(self, rid, **params):
        if request.httprequest.method == "GET":
            return self.usage_get(rid, **params)
        if request.httprequest.method == "PATCH":
            return self.usage_patch(rid, **params)
        return self.usage_delete(rid, **params)


class TMFUsageSpecificationController(http.Controller):

    @http.route('/tmf-api/usageManagement/v4/usageSpecification', type='http', auth='public', methods=['GET'], csrf=False)
    def spec_list(self, **params):
        Model = request.env['tmf.usage.specification'].sudo()

        # ✅ CTK uses ?id=<uuid> as well
        domain = []
        if "id" in params:
            domain.append(("tmf_id", "=", params["id"]))
        else:
            if "name" in params:
                domain.append(("name", "=", params["name"]))
            if "lifecycleStatus" in params:
                domain.append(("lifecycle_status", "=", params["lifecycleStatus"]))
            if "version" in params:
                domain.append(("version", "=", params["version"]))

        offset = int(params.get("offset", 0) or 0)
        limit = int(params.get("limit", 0) or 0) or None

        recs = Model.search(domain, offset=offset, limit=limit)
        fields_csv = params.get("fields")
        return _json_response([_only_fields(r.to_tmf_json(), fields_csv) for r in recs])

    @http.route('/tmf-api/usageManagement/v4/usageSpecification/<string:rid>', type='http', auth='public', methods=['GET'], csrf=False)
    def spec_get(self, rid, **params):
        Model = request.env['tmf.usage.specification'].sudo()

        rec = _find_by_rid(Model, rid)
        if not rec or not rec.exists():
            return _json_response({"error": "Not found"}, status=404)

        return _json_response(_only_fields(rec.to_tmf_json(), params.get("fields")))

    @http.route('/tmf-api/usageManagement/v4/usageSpecification', type='http', auth='public', methods=['POST'], csrf=False)
    def spec_create(self, **params):
        try:
            data = _parse_body()
            vals = {
                "name": data.get("name"),
                "description": data.get("description"),
                "is_bundle": bool(data.get("isBundle")) if data.get("isBundle") is not None else False,
                "last_update": data.get("lastUpdate"),
                "lifecycle_status": data.get("lifecycleStatus"),
                "version": data.get("version"),
            }
            if not vals["name"]:
                return _json_response({"error": "name is required"}, status=400)

            rec = request.env["tmf.usage.specification"].sudo().create(vals)
            tmf_id = rec.tmf_id or str(rec.id)
            loc = f"/tmf-api/usageManagement/v4/usageSpecification/{tmf_id}"
            return _json_response(rec.to_tmf_json(), status=201, extra_headers=_location(loc))
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    @http.route('/tmf-api/usageManagement/v4/usageSpecification/<string:rid>', type='http', auth='public', methods=['PATCH'], csrf=False)
    def spec_patch(self, rid, **params):
        try:
            data = _parse_body()
            Model = request.env['tmf.usage.specification'].sudo()

            rec = _find_by_rid(Model, rid)
            if not rec or not rec.exists():
                return _json_response({"error": "Not found"}, status=404)

            vals = {}
            if "name" in data: vals["name"] = data["name"]
            if "description" in data: vals["description"] = data["description"]
            if "isBundle" in data: vals["is_bundle"] = bool(data["isBundle"])
            if "lastUpdate" in data: vals["last_update"] = data["lastUpdate"]
            if "lifecycleStatus" in data: vals["lifecycle_status"] = data["lifecycleStatus"]
            if "version" in data: vals["version"] = data["version"]

            if vals:
                rec.write(vals)

            return _json_response(_only_fields(rec.to_tmf_json(), params.get("fields")))
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    @http.route('/tmf-api/usageManagement/v4/usageSpecification/<string:rid>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def spec_delete(self, rid, **params):
        Model = request.env['tmf.usage.specification'].sudo()
        rec = _find_by_rid(Model, rid)
        if not rec or not rec.exists():
            return _json_response({"error": "Not found"}, status=404)
        rec.unlink()
        return _json_response({}, status=204)
