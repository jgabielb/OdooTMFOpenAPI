from odoo import http, fields
from odoo.http import request
import json
from odoo.fields import Datetime as OdooDatetime
from datetime import datetime, timedelta

BASE = "/tmf-api/serviceOrdering/v4/serviceOrder"

FORBIDDEN_ON_CREATE = {
    "state", "orderDate", "completionDate"
}

NON_PATCHABLE = {
    "id", "href", "orderDate", "completionDate",
    "cancellationDate", "cancellationReason",
    "@type", "@schemaLocation", "@baseType",
    "milestone", "jeopardyAlert", "errorMessage"
}

def _parse_iso_dt(s: str):
    """
    Accepts: 2026-01-27T15:01:48
             2026-01-27T15:01:48Z
             2026-01-27T15:01:48+00:00
    Returns naive datetime in server/UTC-like terms (Odoo stores naive).
    """
    if not s:
        return None
    s = str(s).strip()

    # strip wrapping quotes (CTK sends orderDate="....")
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()

    # normalize Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None

    # Odoo stores naive UTC; make naive
    if dt.tzinfo:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def _json_response(payload, status=200, extra_headers=None):
    headers = [("Content-Type", "application/json")]
    if extra_headers:
        headers.extend(extra_headers)
    return request.make_response(json.dumps(payload), status=status, headers=headers)


def _json_error(status, reason, message):
    return _json_response({"code": str(status), "reason": reason, "message": message}, status=status)

class TMF641Controller(http.Controller):

    @http.route(BASE, type="http", auth="public", methods=["GET"], csrf=False)
    def list_orders(self, **params):
        domain = []

        # filter by id
        if params.get("id"):
            domain.append(("tmf_id", "=", params["id"]))

        # filter by orderDate (range of 1 second to handle DB microseconds)
        raw = params.get("orderDate")
        if raw is not None:
            dt = _parse_iso_dt(raw)
            if dt:
                domain.append(("order_date", ">=", dt))
                domain.append(("order_date", "<", dt + timedelta(seconds=1)))
            else:
                domain.append(("id", "=", -1))

        try:
            limit = max(1, min(int(params.get("limit") or 50), 1000))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(params.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0

        env = request.env["tmf.service.order"].sudo()
        records = env.search(domain, limit=limit, offset=offset, order="id asc")
        total = env.search_count(domain)

        items = []
        for r in records:
            obj = r.to_tmf_json()
            if obj.get("orderDate") is None:
                obj["orderDate"] = OdooDatetime.now().isoformat()
            items.append(obj)

        # fields selection
        fields_param = params.get("fields")
        if fields_param:
            wanted = {f.strip() for f in str(fields_param).split(",") if f.strip()}
            # Always keep TMF mandatory fields
            wanted |= {"id", "href", "@type"}
            items = [{k: v for k, v in it.items() if k in wanted} for it in items]

        return _json_response(items, extra_headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(items))),
        ])

    @http.route(BASE + "/<string:oid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_order(self, oid):
        rec = request.env["tmf.service.order"].sudo().search([("tmf_id", "=", oid)], limit=1)
        if not rec:
            return _json_error(404, "Not Found", "ServiceOrder not found")
        obj = rec.to_tmf_json()
        if obj.get("orderDate") is None:
            obj["orderDate"] = OdooDatetime.now().isoformat()
        return _json_response(obj)

    @http.route(BASE, type="http", auth="public", methods=["POST"], csrf=False)
    def create_order(self):
        data = json.loads(request.httprequest.data or "{}")

        if "serviceOrderItem" not in data or not data["serviceOrderItem"]:
            return _json_error(400, "Bad Request", "Missing serviceOrderItem")

        for f in FORBIDDEN_ON_CREATE:
            if f in data:
                return _json_error(400, "Bad Request", f"{f} not allowed on POST")

        for item in data["serviceOrderItem"]:
            if not all(k in item for k in ("id", "action", "service")):
                return _json_error(400, "Bad Request", "Invalid serviceOrderItem")

        vals = {
            "external_id": data.get("externalId"),
            "description": data.get("description"),
            "category": data.get("category"),
            "priority": data.get("priority"),
            "requested_start_date": data.get("requestedStartDate"),
            "requested_completion_date": data.get("requestedCompletionDate"),
            "service_order_item": data.get("serviceOrderItem"),
            "related_party": data.get("relatedParty"),
            "note": data.get("note"),
            "external_reference": data.get("externalReference"),

            # server-side set (CTK expects non-null string in responses)
            "order_date": OdooDatetime.now(),
        }

        rec = request.env["tmf.service.order"].sudo().create(vals)

        obj = rec.to_tmf_json()
        if obj.get("orderDate") is None:
            obj["orderDate"] = OdooDatetime.now().isoformat()

        return _json_response(obj, status=201)

    @http.route(BASE + "/<string:oid>", type="http", auth="public",
                methods=["PATCH"], csrf=False)
    def patch_order(self, oid):
        allowed_content_types = {
            "application/merge-patch+json",
            "application/json",
            "application/json-patch+json",
            "application/json-patch-query+json",
        }
        content_type = (request.httprequest.content_type or "").split(";")[0].strip().lower()
        if content_type and content_type not in allowed_content_types:
            return _json_error(415, "Unsupported Media Type", "Invalid Content-Type for PATCH")

        data = json.loads(request.httprequest.data or "{}")

        for f in NON_PATCHABLE:
            if f in data:
                return _json_error(400, "Bad Request", f"{f} is not patchable")

        rec = request.env["tmf.service.order"].sudo().search([("tmf_id", "=", oid)], limit=1)
        if not rec:
            return _json_error(404, "Not Found", "ServiceOrder not found")

        rec.write({
            "description": data.get("description", rec.description),
            "priority": data.get("priority", rec.priority),
            "state": data.get("state", rec.state),
            "requested_start_date": data.get("requestedStartDate", rec.requested_start_date),
            "requested_completion_date": data.get("requestedCompletionDate", rec.requested_completion_date),
            "service_order_item": data.get("serviceOrderItem", rec.service_order_item),
        })

        obj = rec.to_tmf_json()
        if obj.get("orderDate") is None:
            obj["orderDate"] = OdooDatetime.now().isoformat()

        return _json_response(obj)

    @http.route(BASE + "/<string:oid>", type="http", auth="public",
                methods=["DELETE"], csrf=False)
    def delete_order(self, oid):
        rec = request.env["tmf.service.order"].sudo().search([("tmf_id", "=", oid)], limit=1)
        if not rec:
            return _json_error(404, "Not Found", "ServiceOrder not found")
        rec.unlink()
        return request.make_response("", status=204)
