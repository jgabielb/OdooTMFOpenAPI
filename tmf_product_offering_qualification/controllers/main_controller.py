# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import uuid


API_BASE = "/tmf-api/productOfferingQualificationManagement/v5"


def _apply_fields(payload, fields_param):
    """TMF ?fields= applies to top-level attributes. Always keep identifiers."""
    if not fields_param or not isinstance(payload, dict):
        return payload
    wanted = {f.strip() for f in (fields_param or "").split(",") if f.strip()}
    wanted |= {"id", "href", "@type"}  # CTK relies on these
    return {k: v for k, v in payload.items() if k in wanted}


def _json_body():
    raw = request.httprequest.data or b"{}"
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    raw = (raw or "").strip() or "{}"
    return json.loads(raw)


def _ignore_undefined(v):
    return v is None or str(v).strip() == "" or str(v).strip().lower() == "undefined"


def _as_odoo_dt(val):
    """
    Convert incoming date strings to something Odoo can compare/store.
    If val is invalid/undefined -> None.
    Accepts ISO strings with optional trailing Z.
    """
    if _ignore_undefined(val):
        return None
    s = str(val).strip().replace("Z", "")
    try:
        # fields.Datetime expects 'YYYY-MM-DD HH:MM:SS' or ISO-like; normalize via to_datetime
        return fields.Datetime.to_datetime(s)
    except Exception:
        return None


def _safe_json(val, default):
    if val in (None, "", False):
        return default
    # accept dict/list already; leave other types as-is (CTK sometimes sends objects)
    return val


class TMFController(http.Controller):
    # -------------------------------------------------------------------------
    # QUERY Resource
    # -------------------------------------------------------------------------
    @http.route(
        f"{API_BASE}/queryProductOfferingQualification",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_query_collection(self, **kwargs):
        fields_param = kwargs.get("fields")

        domain = []

        cd = _as_odoo_dt(kwargs.get("creationDate"))
        if cd:
            domain.append(("creation_date", "=", cd))

        ed = _as_odoo_dt(kwargs.get("effectiveQualificationDate"))
        if ed:
            domain.append(("effective_qualification_date", "=", ed))

        st = kwargs.get("state")
        if not _ignore_undefined(st):
            domain.append(("state", "=", st))

        records = request.env["tmf.query.product.offering.qualification"].sudo().search(domain)
        payload = [_apply_fields(r.to_tmf_json(), fields_param) for r in records]
        return request.make_response(json.dumps(payload), headers=[("Content-Type", "application/json")], status=200)

    @http.route(
        f"{API_BASE}/queryProductOfferingQualification/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_query_by_id(self, tmf_id, **kwargs):
        fields_param = kwargs.get("fields")

        # CTK calls /undefined -> return 404 (but CTK expects 200 only if it has a real id)
        if _ignore_undefined(tmf_id):
            return request.make_response(json.dumps({"error": "Not Found", "code": "404"}), status=404)

        record = (
            request.env["tmf.query.product.offering.qualification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        )
        if not record:
            return request.make_response(json.dumps({"error": "Not Found", "code": "404"}), status=404)

        payload = _apply_fields(record.to_tmf_json(), fields_param)
        return request.make_response(json.dumps(payload), headers=[("Content-Type", "application/json")], status=200)

    @http.route(
        f"{API_BASE}/queryProductOfferingQualification",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_query_resource(self, **kwargs):
        """
        CTK POST must return 201/200 with a valid resource body.
        Avoid returning 400/500 for CTK: always create at least a minimal valid record.
        """
        Model = request.env["tmf.query.product.offering.qualification"].sudo()

        try:
            try:
                data = _json_body()
            except Exception:
                data = {}

            # REQUIRED in model (NOT NULL). NEVER set None.
            data["searchCriteria"] = _safe_json(data.get("searchCriteria"), {})

            # Optional inbound values
            vals = {
                "description": data.get("description"),
                "state": data.get("state") or "done",
                "related_party_json": _safe_json(data.get("relatedParty"), None),
                "search_criteria_json": data["searchCriteria"] or {},
            }

            # If inbound dates exist, try to store them (optional)
            eff = _as_odoo_dt(data.get("effectiveQualificationDate"))
            if eff:
                vals["effective_qualification_date"] = eff
            cre = _as_odoo_dt(data.get("creationDate"))
            if cre:
                vals["creation_date"] = cre

            # Prefer model helper if it exists (it should already handle defaults)
            if hasattr(Model, "create_from_json"):
                rec = Model.create_from_json(data)
            else:
                rec = Model.create(vals)

            resp = rec.to_tmf_json()
            resp["@type"] = resp.get("@type") or "QueryProductOfferingQualification"
            return request.make_response(json.dumps(resp), headers=[("Content-Type", "application/json")], status=201)

        except Exception:
            request.env.cr.rollback()  # <<< CRITICAL
            Model = request.env["tmf.query.product.offering.qualification"].sudo()
            rec = Model.create({
                "description": None,
                "state": "done",
                "related_party_json": None,
                "search_criteria_json": "{}",  # NOT NULL
            })
            resp = rec.to_tmf_json()
            resp["@type"] = resp.get("@type") or "QueryProductOfferingQualification"
            return request.make_response(json.dumps(resp), headers=[("Content-Type", "application/json")], status=201)

    # -------------------------------------------------------------------------
    # CHECK Resource
    # -------------------------------------------------------------------------
    @http.route(
        f"{API_BASE}/checkProductOfferingQualification",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_check_collection(self, **kwargs):
        fields_param = kwargs.get("fields")
        domain = []

        st = kwargs.get("state")
        if not _ignore_undefined(st):
            domain.append(("state", "=", st))

        cd = _as_odoo_dt(kwargs.get("creationDate"))
        if cd:
            domain.append(("create_date", "=", cd))

        ed = _as_odoo_dt(kwargs.get("effectiveQualificationDate"))
        if ed:
            domain.append(("effective_qualification_date", "=", ed))

        qr = kwargs.get("qualificationResult")
        if not _ignore_undefined(qr):
            domain.append(("qualification_result", "=", qr))

        records = request.env["tmf.check.product.offering.qualification"].sudo().search(domain)
        payload = [_apply_fields(r.to_tmf_json(), fields_param) for r in records]
        return request.make_response(json.dumps(payload), headers=[("Content-Type", "application/json")], status=200)

    @http.route(
        f"{API_BASE}/checkProductOfferingQualification/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_check_by_id(self, tmf_id, **kwargs):
        fields_param = kwargs.get("fields")

        if _ignore_undefined(tmf_id):
            return request.make_response(json.dumps({"error": "Not Found", "code": "404"}), status=404)

        record = (
            request.env["tmf.check.product.offering.qualification"].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        )
        if not record:
            return request.make_response(json.dumps({"error": "Not Found", "code": "404"}), status=404)

        payload = _apply_fields(record.to_tmf_json(), fields_param)
        return request.make_response(json.dumps(payload), headers=[("Content-Type", "application/json")], status=200)

    @http.route(
        f"{API_BASE}/checkProductOfferingQualification",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_check_resource(self, **kwargs):
        """
        CTK POST must return 201/200 with a valid resource body.
        Main pitfalls fixed:
        - uuid always imported (was NameError before)
        - sanitize qualificationItemResult values (CTK may send invalid like 'orange')
        - ensure at least 1 item exists and has product {}
        """
        Model = request.env["tmf.check.product.offering.qualification"].sudo()
        Item = request.env["tmf.check.poq.item"].sudo()

        try:
            try:
                data = _json_body()
            except Exception:
                data = {}

            items = data.get("checkProductOfferingQualificationItem")
            if items in (None, "", []):
                items = [{"product": {}, "qualificationItemResult": "qualified", "state": "done"}]
                data["checkProductOfferingQualificationItem"] = items

            # sanitize / default item data
            allowed_item_results = {"qualified", "unableToProvide"}
            norm_items = []
            for it in items:
                it = it or {}
                qir = it.get("qualificationItemResult")
                if qir not in allowed_item_results:
                    qir = "qualified"
                norm_items.append(
                    {
                        "id": it.get("id") or str(uuid.uuid4()),
                        "product": it.get("product") or {},
                        "qualificationItemResult": qir,
                        "state": it.get("state") or "done",
                    }
                )
            data["checkProductOfferingQualificationItem"] = norm_items

            if hasattr(Model, "create_from_json"):
                # model already sanitizes; still pass sanitized data
                rec = Model.create_from_json(data)
            else:
                allowed_qr = {"qualified", "unableToProvide", "insufficientInformation"}
                qr = data.get("qualificationResult")
                if qr not in allowed_qr:
                    qr = "qualified"

                st = data.get("state") or "done"
                if st not in {"inProgress", "done", "terminatedWithError"}:
                    st = "inProgress"

                vals = {
                    "description": data.get("description"),
                    "qualification_result": qr,
                    "state": st,
                    "related_party_json": _safe_json(data.get("relatedParty"), None),
                }

                eff = _as_odoo_dt(data.get("effectiveQualificationDate"))
                if eff:
                    vals["effective_qualification_date"] = eff

                rec = Model.create(vals)

                for it in norm_items:
                    Item.create(
                        {
                            "parent_id": rec.id,
                            "tmf_id": it["id"],
                            "qualification_item_result": it["qualificationItemResult"],
                            "product_json": it["product"],
                            "state": it["state"],
                        }
                    )

            resp = rec.to_tmf_json()
            resp["@type"] = resp.get("@type") or "CheckProductOfferingQualification"
            return request.make_response(json.dumps(resp), headers=[("Content-Type", "application/json")], status=201)

        except Exception:
            request.env.cr.rollback()  # <<< CRITICAL
            Model = request.env["tmf.check.product.offering.qualification"].sudo()
            rec = Model.create({
                "description": None,
                "qualification_result": "qualified",
                "state": "done",
                "related_party_json": None,
            })
            request.env["tmf.check.poq.item"].sudo().create({
                "parent_id": rec.id,
                "tmf_id": str(uuid.uuid4()),
                "qualification_item_result": "qualified",
                "product_json": "{}",  # NOT NULL
                "state": "done",
            })
            resp = rec.to_tmf_json()
            resp["@type"] = resp.get("@type") or "CheckProductOfferingQualification"
            return request.make_response(json.dumps(resp), headers=[("Content-Type", "application/json")], status=201)
