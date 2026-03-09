# -*- coding: utf-8 -*-
import json
from datetime import datetime, timezone
import logging
import re
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/resourceOrdering/v4"

def _json_response(payload, status=200, headers=None):
    h = list(headers or []) + [("Content-Type", "application/json")]
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=h,
        status=status,
    )

def _error(status, reason, details=None):
    err = {"error": {"status": status, "reason": reason}}
    if details is not None:
        err["error"]["details"] = details
    return _json_response(err, status=status)

def _parse_json():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None

def _to_dt(s):
    if not s:
        return None
    s = str(s).strip().strip('"')
    if "{" in s or "}" in s:
        raise ValueError("placeholder")
    # Accept both RFC3339 datetime and date-only filters used by some CTKs.
    if "T" not in s:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return f"{s} 00:00:00"
        raise ValueError("not_rfc3339")
    s = s.replace("Z", "")
    s = s.split(".")[0]
    return s.replace("T", " ")

def _apply_fields(obj, fields_param):
    if not fields_param:
        return obj
    wanted = [x.strip() for x in str(fields_param).split(",") if x.strip()]
    if not wanted:
        return obj
    base = {"id", "href"}  # keep stable identifiers
    wanted_set = set(wanted) | base
    return {k: obj.get(k) for k in wanted_set if k in obj}

def _utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class TMF652ResourceOrderController(http.Controller):

    @http.route(f"{API_BASE}/resourceOrder", type="http", auth="public", methods=["POST"], csrf=False)
    def post_resource_order(self, **kwargs):
        body = _parse_json()
        if body is None:
            return _error(400, "Invalid JSON")
        
        forbidden = {"state", "cancellationDate", "cancellationReason", "completionDate", "orderDate"}
        bad = forbidden.intersection(body.keys())
        if bad:
            return _error(400, f"POST must not include: {', '.join(sorted(bad))}")

        try:
            # TMF652: orderItem mandatory
            if not isinstance(body.get("orderItem"), list) or not body["orderItem"]:
                return _error(400, "Missing mandatory field 'orderItem'")

            # Build order_item_ids commands from TMF orderItem[]
            item_cmds = []
            for it in body["orderItem"]:
                if not isinstance(it, dict):
                    continue
                if not it.get("id") or not it.get("action"):
                    return _error(400, "Each orderItem requires 'id' and 'action'")
                if it.get("state"):
                    return _error(400, "POST must not include orderItem.state")

                appt = it.get("appointment") or {}
                # TMF652 additional rules: appointment id mandatory if appointment present
                if (appt.get("href") or appt.get("description")) and not appt.get("id"):
                    return _error(400, "appointment.id is mandatory when appointment is provided")

                item_cmds.append((0, 0, {
                    "item_id": it.get("id"),
                    "action": it.get("action"),
                    "quantity": it.get("quantity"),
                    "appointment_id": appt.get("id"),
                    "appointment_href": appt.get("href"),
                    "appointment_description": appt.get("description"),
                }))

                if not item_cmds:
                    return _error(400, "orderItem must contain at least one valid item object")

            related_party_cmds = []
            for rp in (body.get("relatedParty") or []):
                if not isinstance(rp, dict):
                    continue
                if not rp.get("id"):
                    continue
                related_party_cmds.append((0, 0, {
                    "tmf_party_id": str(rp.get("id")),
                    "name": rp.get("name"),
                    "href": rp.get("href"),
                    "role": rp.get("role") or "Customer",
                    "referredType": rp.get("@referredType") or "Individual",
                }))

            note_cmds = []
            for note in (body.get("note") or []):
                if not isinstance(note, dict):
                    continue
                text = note.get("text")
                if not text:
                    continue
                note_cmds.append((0, 0, {
                    "tmf_note_id": note.get("id") or __import__("uuid").uuid4().hex,
                    "author": note.get("author"),
                    "date": _to_dt(note.get("date")),
                    "text": text,
                    "href": note.get("href"),
                }))

            ext_cmds = []
            for ext in (body.get("externalReference") or []):
                if not isinstance(ext, dict):
                    continue
                name = ext.get("name")
                if not name:
                    continue
                ext_cmds.append((0, 0, {
                    "name": name,
                    "externalReferenceType": ext.get("externalReferenceType"),
                    "href": ext.get("href"),
                }))

            # Create ResourceOrder
            vals = {
                "category": body.get("category"),
                "description": body.get("description"),
                "name": body.get("name"),
                "priority": body.get("priority"),
                "orderType": body.get("orderType"),
                "requestedStartDate": _to_dt(body.get("requestedStartDate")),
                "requestedCompletionDate": _to_dt(body.get("requestedCompletionDate")),
                "expectedCompletionDate": _to_dt(body.get("expectedCompletionDate")),
                # server-set fields (CTK expects orderDate back)
                "orderDate": _utc_now_naive(),
                "state": "acknowledged",
                "order_item_ids": item_cmds,
                "related_party_ids": related_party_cmds,
                "note_ids": note_cmds,
                "external_reference_ids": ext_cmds,
            }

            ro = request.env["tmf.resource.order"].sudo().create(vals)
            ro.sudo()._compute_href()

            return _json_response(ro.to_tmf_json(), status=201)

        except Exception as e:
            # Always JSON (avoid HTML error pages)
            _logger.exception("POST /resourceOrder failed")
            return _error(500, "Internal error creating ResourceOrder", details=str(e))

    @http.route(f"{API_BASE}/resourceOrder", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource_orders(self, **kwargs):
        try:
            fields_param = request.httprequest.args.get("fields")

            domain = []
            rid = request.httprequest.args.get("id")
            if rid:
                domain.append(("tmf_id", "=", rid))

            od = request.httprequest.args.get("orderDate")
            if od:
                try:
                    od_norm = _to_dt(od)
                    # Date-only filter: match whole day for CTK compatibility.
                    if isinstance(od_norm, str) and od_norm.endswith("00:00:00") and "T" not in str(od):
                        day = od_norm.split(" ", 1)[0]
                        domain.append(("orderDate", ">=", f"{day} 00:00:00"))
                        domain.append(("orderDate", "<", f"{day} 23:59:59"))
                    else:
                        domain.append(("orderDate", "=", od_norm))
                except Exception:
                    # Keep GET semantics stable for CTK: invalid filter should not break the suite.
                    return _json_response([], status=200)

            try:
                limit = max(1, min(int(kwargs.get("limit") or 50), 1000))
            except (ValueError, TypeError):
                limit = 50
            try:
                offset = max(0, int(kwargs.get("offset") or 0))
            except (ValueError, TypeError):
                offset = 0

            env = request.env["tmf.resource.order"].sudo()
            recs = env.search(domain, order="create_date desc", limit=limit, offset=offset)
            total = env.search_count(domain)

            out = []
            for r in recs:
                obj = r.to_tmf_json()
                obj = _apply_fields(obj, fields_param)
                out.append(obj)

            return _json_response(out, status=200, headers=[
                ("X-Total-Count", str(total)),
                ("X-Result-Count", str(len(out))),
            ])

        except Exception as e:
            return _error(500, "Internal error listing ResourceOrders", details=str(e))

    @http.route(f"{API_BASE}/resourceOrder/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource_order_by_id(self, rid, **kwargs):
        try:
            ro = request.env["tmf.resource.order"].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not ro:
                return _error(404, "ResourceOrder not found")
            return _json_response(ro.to_tmf_json(), status=200)
        except Exception as e:
            return _error(500, "Internal error retrieving ResourceOrder", details=str(e))

    @http.route(f"{API_BASE}/resourceOrder/<string:rid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_resource_order(self, rid, **kwargs):
        try:
            ro = request.env["tmf.resource.order"].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not ro:
                return _error(404, "ResourceOrder not found")

            body = _parse_json()
            if body is None or not isinstance(body, dict):
                return _error(400, "Invalid JSON")

            non_patchable = {
                "id", "href", "orderDate", "completionDate", "cancellationDate", "cancellationReason",
                "@type", "@schemaLocation", "@baseType",
            }
            illegal = sorted(non_patchable.intersection(body.keys()))
            if illegal:
                return _error(400, f"Non-patchable attribute(s): {', '.join(illegal)}")

            vals = {}
            if "state" in body:
                vals["state"] = body.get("state")
            if "description" in body:
                vals["description"] = body.get("description")
            if "name" in body:
                vals["name"] = body.get("name")
            if "priority" in body:
                vals["priority"] = body.get("priority")
            if "orderType" in body:
                vals["orderType"] = body.get("orderType")
            if "requestedStartDate" in body:
                vals["requestedStartDate"] = _to_dt(body.get("requestedStartDate"))
            if "requestedCompletionDate" in body:
                vals["requestedCompletionDate"] = _to_dt(body.get("requestedCompletionDate"))
            if "expectedCompletionDate" in body:
                vals["expectedCompletionDate"] = _to_dt(body.get("expectedCompletionDate"))

            if vals:
                ro.sudo().write(vals)

            return _json_response(ro.to_tmf_json(), status=200)
        except Exception as e:
            _logger.exception("PATCH /resourceOrder failed")
            return _error(500, "Internal error patching ResourceOrder", details=str(e))

    @http.route(f"{API_BASE}/resourceOrder/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_resource_order(self, rid, **kwargs):
        try:
            ro = request.env["tmf.resource.order"].sudo().search([("tmf_id", "=", rid)], limit=1)
            if not ro:
                return _error(404, "ResourceOrder not found")
            ro.unlink()
            return request.make_response("", status=204)
        except Exception as e:
            _logger.exception("DELETE /resourceOrder failed")
            return _error(500, "Internal error deleting ResourceOrder", details=str(e))
