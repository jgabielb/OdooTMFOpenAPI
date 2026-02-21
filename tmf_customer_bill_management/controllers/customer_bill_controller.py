# -*- coding: utf-8 -*-
import json
from odoo import http, fields
from odoo.http import request

API_BASE = "/tmf-api/customerBillManagement/v5"

RESOURCES = {
    "appliedCustomerBillingRate": {"model": "tmf.applied.customer.billing.rate", "type": "AppliedCustomerBillingRate"},
    "billCycle": {"model": "tmf.bill.cycle", "type": "BillCycle"},
    "customerBill": {"model": "tmf.customer.bill", "type": "CustomerBill"},
    "customerBillOnDemand": {"model": "tmf.customer.bill.on.demand", "type": "CustomerBillOnDemand"},
}

def _host_url():
    return request.httprequest.host_url.rstrip("/")

def _parse_fields_param():
    fields_q = (request.httprequest.args.get("fields") or "").strip()
    if not fields_q:
        return None
    return {f.strip() for f in fields_q.split(",") if f.strip()}

def _apply_fields_filter(obj: dict, fields_filter: set | None):
    if not fields_filter:
        return obj
    keep = set(fields_filter) | {"href", "id", "@type"}
    return {k: v for k, v in obj.items() if k in keep}

def _dt_iso_z(dtval):
    if not dtval:
        return None
    if isinstance(dtval, str):
        s = dtval.strip()
        s = s.replace(" ", "T") if " " in s and "T" not in s else s
        return s if s.endswith("Z") else (s + "Z" if "T" in s else s)
    return fields.Datetime.to_string(dtval).replace(" ", "T") + "Z"

def _json_body_or_400():
    raw = request.httprequest.data or b""
    try:
        txt = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        txt = (txt or "").strip()
        if not txt:
            return {}
        return json.loads(txt)
    except Exception:
        return None

def _parse_dt_for_domain(val: str):
    """
    CTK sometimes sends placeholder values like 'lastUpdate', 'billingDate', 'date'.
    Never raise here. Return a datetime or None.
    Accepts: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS(.sss)Z, or with space.
    """
    if not val:
        return None

    s = (val or "").strip()
    if not s:
        return None

    # Ignore CTK placeholder literals (and similar non-date tokens)
    lowered = s.lower()
    if lowered in {"lastupdate", "billingdate", "date", "chargedate", "creditdate", "mailingdate", "paymentduedate"}:
        return None

    # Normalize
    s = s.replace("Z", "").replace("T", " ").strip()

    # If only date is provided, extend to datetime
    if len(s) == 10 and s[4] == "-" and s[7] == "-":  # YYYY-MM-DD
        s = s + " 00:00:00"

    try:
        return fields.Datetime.to_datetime(s)
    except Exception:
        return None

class TMF678CustomerBillController(http.Controller):

    def _seed_if_empty(self, resource: str, model):
        """
        Seed 1 record for CTK when collection is empty.
        Only uses fields that exist in the model.
        """
        if resource not in ("billCycle", "appliedCustomerBillingRate"):
            return
        if model.search([], limit=1):
            return

        now = fields.Datetime.now()
        vals = {
            "tmf_type": RESOURCES[resource]["type"],
            "last_update": now,
            "payload": {},
        }

        # optional fields by model
        if "name" in model._fields:
            vals["name"] = f"seed-{resource}"
        if resource == "billCycle" and "billing_date" in model._fields:
            vals["billing_date"] = now
        if resource == "appliedCustomerBillingRate":
            if "date" in model._fields:
                vals["date"] = now
            if "is_billed" in model._fields:
                vals["is_billed"] = False

        # remove any keys not present (safety)
        vals = {k: v for k, v in vals.items() if k in model._fields}

        rec = model.create(vals)
        if "href" in model._fields:
            try:
                rec.href = rec._compute_href(_host_url(), API_BASE)
            except Exception:
                pass

    # -----------------------
    # GET collection
    # -----------------------
    @http.route(
        [f"{API_BASE}/<string:resource>"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_collection(self, resource, **kwargs):
        if resource not in RESOURCES:
            return request.make_response("Not Found", headers=[("Content-Type", "text/plain")], status=404)

        fields_filter = _parse_fields_param()
        model = request.env[RESOURCES[resource]["model"]].sudo()

        # seed FIRST
        self._seed_if_empty(resource, model)

        domain = []

        # filtering
        if resource == "customerBillOnDemand":
            ba = request.httprequest.args.get("billingAccount")
            if ba:
                domain.append(("billing_account_id", "=", ba))

            st = request.httprequest.args.get("state")
            if st:
                domain.append(("state", "=", st))

            lu = request.httprequest.args.get("lastUpdate")
            if lu:
                dt = _parse_dt_for_domain(lu)
                if dt:
                    domain.append(("last_update", ">=", dt))

        if resource == "appliedCustomerBillingRate":
            d = request.httprequest.args.get("date")
            if d:
                dt = _parse_dt_for_domain(d)
                if dt and "date" in model._fields:
                    domain.append(("date", ">=", dt))

            ib = request.httprequest.args.get("isBilled")
            if ib is not None and "is_billed" in model._fields:
                if ib.lower() in ("true", "false", "1", "0"):
                    domain.append(("is_billed", "=", ib.lower() in ("true", "1")))

        if resource == "billCycle":
            bd = request.httprequest.args.get("billingDate")
            if bd:
                dt = _parse_dt_for_domain(bd)
                if dt and "billing_date" in model._fields:
                    domain.append(("billing_date", ">=", dt))

            nm = request.httprequest.args.get("name")
            if nm and "name" in model._fields:
                domain.append(("name", "ilike", nm))

        recs = model.search(domain, limit=200)

        out = [_apply_fields_filter(self._to_tmf(resource, r), fields_filter) for r in recs]
        return request.make_response(json.dumps(out), headers=[("Content-Type", "application/json")], status=200)

    # -----------------------
    # GET by id
    # -----------------------
    @http.route(
        [f"{API_BASE}/<string:resource>/<string:tmf_id>"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_one(self, resource, tmf_id, **kwargs):
        if resource not in RESOURCES:
            return request.make_response("Not Found", headers=[("Content-Type", "text/plain")], status=404)

        fields_filter = _parse_fields_param()
        model = request.env[RESOURCES[resource]["model"]].sudo()
        rec = model.search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return request.make_response("Not Found", headers=[("Content-Type", "text/plain")], status=404)

        body = _apply_fields_filter(self._to_tmf(resource, rec), fields_filter)
        return request.make_response(json.dumps(body), headers=[("Content-Type", "application/json")], status=200)

    # -----------------------
    # POST /customerBillOnDemand
    # -----------------------
    @http.route(
        [f"{API_BASE}/customerBillOnDemand"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def post_customer_bill_on_demand(self, **kwargs):
        payload = _json_body_or_400()
        if payload is None:
            return request.make_response(json.dumps({"error": "Invalid JSON body"}), headers=[("Content-Type", "application/json")], status=400)

        tmf_type = payload.get("@type")
        billing_account = payload.get("billingAccount") or {}
        ba_id = billing_account.get("id")
        ba_type = billing_account.get("@type")

        if not tmf_type or not ba_id or not ba_type:
            return request.make_response(
                json.dumps({"error": "Missing mandatory fields: @type, billingAccount.id, billingAccount.@type"}),
                headers=[("Content-Type", "application/json")],
                status=400,
            )

        model = request.env["tmf.customer.bill.on.demand"].sudo()
        rec = model.create({
            "tmf_type": tmf_type,
            "billing_account_id": str(ba_id),
            "billing_account_type": str(ba_type),
            "state": payload.get("state") or "inProgress",  # Default to inProgress for CTK safety
            "payload": payload,
            "last_update": fields.Datetime.now(),
        })

        rec.href = rec._compute_href(_host_url(), API_BASE)

        body = self._to_tmf("customerBillOnDemand", rec)
        return request.make_response(json.dumps(body), headers=[("Content-Type", "application/json")], status=201)

    # -----------------------
    # PATCH /customerBill/{id}
    # -----------------------
    @http.route(
        [f"{API_BASE}/customerBill/<string:tmf_id>"],
        type="http",
        auth="public",
        methods=["PATCH"],
        csrf=False,
    )
    def patch_customer_bill(self, tmf_id, **kwargs):
        payload = _json_body_or_400()
        if payload is None:
            return request.make_response(json.dumps({"error": "Invalid JSON body"}), headers=[("Content-Type", "application/json")], status=400)

        model = request.env["tmf.customer.bill"].sudo()
        rec = model.search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return request.make_response("Not Found", headers=[("Content-Type", "text/plain")], status=404)

        try:
            rec.apply_patch(payload)
        except ValueError as e:
            return request.make_response(json.dumps({"error": str(e)}), headers=[("Content-Type", "application/json")], status=400)

        rec.href = rec._compute_href(_host_url(), API_BASE)

        body = self._to_tmf("customerBill", rec)
        # Conformance Page 18: Status Code 200 if resource modified
        return request.make_response(json.dumps(body), headers=[("Content-Type", "application/json")], status=200)

    # -----------------------
    # TMF serialization
    # -----------------------
    def _to_tmf(self, resource: str, rec):
        host = _host_url()

        if resource == "billCycle":
            href = rec.href or rec._compute_href(host, API_BASE)
            
            # MANDATORY: billingDate must be string. Fallback to STABLE values (create_date/last_update)
            b_date = _dt_iso_z(getattr(rec, "billing_date", None))
            if not b_date:
                fallback = getattr(rec, "create_date", None) or getattr(rec, "last_update", None) or fields.Datetime.now()
                b_date = _dt_iso_z(fallback)

            base = {
                "id": rec.tmf_id,
                "href": href,
                "@type": rec.tmf_type or "BillCycle",
                "name": getattr(rec, "name", None),
                "billingDate": b_date,
                "lastUpdate": _dt_iso_z(getattr(rec, "last_update", None)),
            }
            base.update(rec.payload or {})
            base["id"] = rec.tmf_id
            base["href"] = href
            base["@type"] = rec.tmf_type or "BillCycle"
            return base

        if resource == "appliedCustomerBillingRate":
            href = rec.href or rec._compute_href(host, API_BASE)
            
            # MANDATORY: date must be string.
            r_date = _dt_iso_z(getattr(rec, "date", None))
            if not r_date:
                fallback = getattr(rec, "create_date", None) or getattr(rec, "last_update", None) or fields.Datetime.now()
                r_date = _dt_iso_z(fallback)

            base = {
                "id": rec.tmf_id,
                "href": href,
                "@type": rec.tmf_type or "AppliedCustomerBillingRate",
                "date": r_date,
                "isBilled": bool(getattr(rec, "is_billed", False)),
                "lastUpdate": _dt_iso_z(getattr(rec, "last_update", None)),
            }
            base.update(rec.payload or {})
            base["id"] = rec.tmf_id
            base["href"] = href
            base["@type"] = rec.tmf_type or "AppliedCustomerBillingRate"
            return base

        if resource == "customerBill":
            # Delegate to model method to ensure billDocument and notification logic reuse correct structure
            return rec.to_tmf_json()

        if resource == "customerBillOnDemand":
            return rec.to_tmf_json(host_url=host, api_base=API_BASE)

        return {}