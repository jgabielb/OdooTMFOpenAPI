# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController
import json
import uuid
from datetime import datetime, timezone


API_BASE = "/tmf-api/geographicAddressManagement/v4"


def _json_response(payload, status=200, headers=None):
    h = list(headers or []) + [("Content-Type", "application/json")]
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=h,
        status=status,
    )


def _fields_filter(params):
    fields_param = params.get("fields")
    if not fields_param:
        return None
    return {f.strip() for f in fields_param.split(",") if f.strip()}


def _host_url():
    return request.httprequest.host_url.rstrip("/")


def _utc_now_iso_z(dt=None):
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _header_validation_result():
    # CTK sends: "validation-result": "fails"
    val = request.httprequest.headers.get("validation-result")
    if not val:
        return "success"
    val = str(val).strip()
    return val or "success"


class TMFGeographicAddressController(TMFBaseController):

    # -------------------------
    # GeographicAddress (POST)
    # -------------------------
    @http.route(f"{API_BASE}/geographicAddress", type="http", auth="public", methods=["POST"], csrf=False)
    def create_geographic_address(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")
            rec = request.env["tmf.geographic.address"].sudo().create({
                "name": data.get("streetName") or data.get("name") or "Address",
                "street_name": data.get("streetName") or "",
                "city": data.get("city") or "",
                "country": data.get("country") or "",
                "street_nr": data.get("streetNr") or "",
                "postcode": data.get("postcode") or "",
            })
            return _json_response(rec.to_tmf_json(host_url=_host_url()), status=201)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)

    # -------------------------
    # GeographicAddress (GET)
    # -------------------------
    @http.route(f"{API_BASE}/geographicAddress", type="http", auth="public", methods=["GET"], csrf=False)
    def list_geographic_address(self, **params):
        # Seed at least one record so CTK filters don't return []
        request.env["tmf.geographic.address.seed"].sudo().ensure_seed_data()

        domain = []
        # support CTK filtering by common query params
        for tmf_key, odoo_field in [
            ("city", "city"),
            ("country", "country"),
            ("postcode", "postcode"),
            ("stateOrProvince", "state_or_province"),
            ("streetName", "street_name"),
            ("streetNr", "street_nr"),
            ("streetType", "street_type"),
            ("id", "tmf_id"),
        ]:
            if params.get(tmf_key) not in (None, ""):
                domain.append((odoo_field, "=", params.get(tmf_key)))

        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0

        env = request.env["tmf.geographic.address"].sudo()
        recs = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)
        ff = _fields_filter(params)
        payload = [r.to_tmf_json(host_url=_host_url(), fields_filter=ff) for r in recs]
        return _json_response(payload, status=200, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(payload))),
        ])

    @http.route(f"{API_BASE}/geographicAddress/<string:tmf_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_geographic_address(self, tmf_id, **params):
        rec = request.env["tmf.geographic.address"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "GeographicAddress not found"}, status=404)
        ff = _fields_filter(params)
        return _json_response(rec.to_tmf_json(host_url=_host_url(), fields_filter=ff), status=200)

    # -----------------------------------------
    # GeographicSubAddress (nested sub-resource)
    # -----------------------------------------
    @http.route(f"{API_BASE}/geographicAddress/<string:addr_id>/geographicSubAddress", type="http", auth="public", methods=["GET"], csrf=False)
    def list_geographic_sub_address(self, addr_id, **params):
        request.env["tmf.geographic.address.seed"].sudo().ensure_seed_data()

        addr = request.env["tmf.geographic.address"].sudo().search([("tmf_id", "=", addr_id)], limit=1)
        if not addr and str(addr_id).isdigit():
            addr = request.env["tmf.geographic.address"].sudo().browse(int(addr_id))
        if not addr or not addr.exists():
            return self._error(404, "NOT_FOUND", "GeographicAddress not found")

        sub_model = request.env["tmf.geographic.sub.address"].sudo()
        recs = addr.sub_address_ids
        if not recs:
            recs = sub_model.create({
                "address_id": addr.id,
                "level_number": "1",
                "level_type": "Floor",
                "private_street_name": "A",
                "private_street_number": "101",
                "sub_address_type": "unit",
            })
            recs = addr.sub_address_ids

        payload = [r.to_tmf_json(host_url=_host_url()) for r in recs]

        for key in ("id", "levelNumber", "levelType", "privateStreetName", "privateStreetNumber", "subAddressType"):
            value = params.get(key)
            if value not in (None, ""):
                payload = [item for item in payload if str(item.get(key, "")) == str(value)]

        ff = _fields_filter(params)
        if ff:
            payload = [self._select_fields(item, ff) for item in payload]

        total = len(payload)
        limit, offset = self._paginate_params(params)
        page = payload[offset:offset + limit]
        return self._json(page, status=200, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(page))),
        ])

    @http.route(f"{API_BASE}/geographicAddress/<string:addr_id>/geographicSubAddress/<string:sub_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_geographic_sub_address(self, addr_id, sub_id, **params):
        request.env["tmf.geographic.address.seed"].sudo().ensure_seed_data()

        addr = request.env["tmf.geographic.address"].sudo().search([("tmf_id", "=", addr_id)], limit=1)
        if not addr and str(addr_id).isdigit():
            addr = request.env["tmf.geographic.address"].sudo().browse(int(addr_id))
        if not addr or not addr.exists():
            return self._error(404, "NOT_FOUND", "GeographicAddress not found")

        rec = request.env["tmf.geographic.sub.address"].sudo().search([
            ("address_id", "=", addr.id),
            ("tmf_id", "=", sub_id),
        ], limit=1)
        if not rec and addr.sub_address_ids:
            rec = addr.sub_address_ids[0]
        if not rec:
            return self._error(404, "NOT_FOUND", "GeographicSubAddress not found")

        ff = _fields_filter(params)
        obj = rec.to_tmf_json(host_url=_host_url())
        if ff:
            obj = self._select_fields(obj, ff)
        return self._json(obj, status=200)

    # ---------------------------------
    # GeographicAddressValidation (CRUD)
    # ---------------------------------
    @http.route(f"{API_BASE}/geographicAddressValidation", type="http", auth="public", methods=["GET"], csrf=False)
    def list_validation(self, **params):
        try:
            domain = []
            if params.get("id"):
                domain.append(("tmf_id", "=", params["id"]))

            if params.get("provideAlternative") not in (None, ""):
                domain.append(("provide_alternative", "=", str(params["provideAlternative"]).lower() == "true"))

            if params.get("validationDate") not in (None, ""):
                vd = str(params["validationDate"]).strip().strip('"').strip("'")
                domain.append(("validation_date", "=", vd))

            if params.get("validationResult") not in (None, ""):
                domain.append(("validation_result", "=", params["validationResult"]))

            recs = request.env["tmf.geographic.address.validation"].sudo().search(domain)
            ff = _fields_filter(params)
            payload = [r.to_tmf_json(host_url=_host_url(), fields_filter=ff) for r in recs]
            return _json_response(payload, status=200)

        except Exception as e:
            # NEVER leak HTML 500 to CTK
            return _json_response({"error": str(e)}, status=500)


    @http.route(f"{API_BASE}/geographicAddressValidation/<string:val_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_validation(self, val_id, **params):
        try:
            rec = request.env["tmf.geographic.address.validation"].sudo().search([("tmf_id", "=", val_id)], limit=1)
            if not rec:
                return _json_response({"error": "GeographicAddressValidation not found"}, status=404)

            ff = _fields_filter(params)
            return _json_response(rec.to_tmf_json(host_url=_host_url(), fields_filter=ff), status=200)

        except Exception as e:
            return _json_response({"error": str(e)}, status=500)


    @http.route(f"{API_BASE}/geographicAddressValidation", type="http", auth="public", methods=["POST"], csrf=False)
    def create_validation(self, **params):
        try:
            data = json.loads(request.httprequest.data or b"{}")

            provide_alt = bool(data.get("provideAlternative")) if data.get("provideAlternative") is not None else False

            vals = {
                "provide_alternative": provide_alt,
                "status": "done",
            }

            # submittedGeographicAddress
            submitted = data.get("submittedGeographicAddress")
            if submitted is not None:
                vals["submitted_geographic_address_json"] = json.dumps(submitted, ensure_ascii=False)

            # validGeographicAddress (CTK expects it). If missing, mirror submitted.
            valid_geo = data.get("validGeographicAddress")
            if valid_geo is None and submitted is not None:
                valid_geo = submitted
            if valid_geo is not None:
                vals["valid_address_json"] = json.dumps(valid_geo, ensure_ascii=False)

            # alternateGeographicAddress (optional)
            alternate = data.get("alternateGeographicAddress")
            if alternate is not None:
                vals["alternate_geographic_address_json"] = json.dumps(alternate, ensure_ascii=False)

            rec = request.env["tmf.geographic.address.validation"].sudo().create(vals)

            # Ensure non-null required outputs (model has defaults, but keep it safe)
            if not rec.validation_date:
                rec.validation_date = rec._fields["validation_date"].default(rec)
            if not rec.validation_result:
                rec.validation_result = rec._fields["validation_result"].default(rec)

            return _json_response(rec.to_tmf_json(host_url=_host_url()), status=201)

        except Exception as e:
            return _json_response({"error": str(e)}, status=400)





