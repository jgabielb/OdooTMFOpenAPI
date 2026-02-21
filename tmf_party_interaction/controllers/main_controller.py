# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

API_BASE = "/tmf-api/partyInteractionManagement/v5"
RESOURCE = "partyInteraction"

def _as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    return []


def _json_body():
    # Works with CTK (application/json) and avoids json.loads on empty bytes
    if getattr(request, "jsonrequest", None):
        return request.jsonrequest or {}
    raw = request.httprequest.data or b"{}"
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw or "{}")


class TMFPartyInteractionController(http.Controller):

    @http.route(f"{API_BASE}/{RESOURCE}", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resources(self, **params):
        records = request.env["tmf.party.interaction"].sudo().search([])
        return request.make_response(
            json.dumps([r.to_tmf_json(host_url=request.httprequest.host_url) for r in records]),
            headers=[("Content-Type", "application/json")],
            status=200,
        )

    @http.route(f"{API_BASE}/{RESOURCE}/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_resource(self, rid, **params):
        rec = request.env["tmf.party.interaction"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return request.make_response("", status=404)
        return request.make_response(
            json.dumps(rec.to_tmf_json(host_url=request.httprequest.host_url)),
            headers=[("Content-Type", "application/json")],
            status=200,
        )

    @http.route(f"{API_BASE}/{RESOURCE}", type="http", auth="public", methods=["POST"], csrf=False)
    def create_resource(self, **params):
        try:
            data = _json_body()

            # TMF683 POST mandatory: direction, reason, relatedChannel, @type :contentReference[oaicite:1]{index=1}
            for k in ("direction", "reason", "relatedChannel", "@type"):
                if not data.get(k):
                    return request.make_response(
                        json.dumps({"error": f"Missing mandatory attribute: {k}"}),
                        headers=[("Content-Type", "application/json")],
                        status=400,
                    )

            # Create using TMF keys -> Odoo fields
            vals = {
                "creation_date": data.get("creationDate"),
                "description": data.get("description"),
                "direction": data.get("direction"),
                "reason": data.get("reason"),
                "status": data.get("status"),
                "status_change_date": data.get("statusChangeDate"),
                "interaction_date": data.get("interactionDate"),
                "tmf_type": data.get("@type"),
                "related_channel": data.get("relatedChannel"),
                "attachment": data.get("attachment"),
                "external_identifier": _as_list(data.get("externalIdentifier")),
                "interaction_item": data.get("interactionItem"),
                "interaction_relationship": data.get("interactionRelationship"),
                "note": data.get("note"),
                "related_party": data.get("relatedParty"),
            }

            # Convert ISO strings to datetime where needed (optional; ok if you keep them as strings too)
            if vals["creation_date"]:
                vals["creation_date"] = request.env["ir.fields.converter"].sudo().to_record(
                    request.env["tmf.party.interaction"], "creation_date", vals["creation_date"]
                )
            if vals["status_change_date"]:
                vals["status_change_date"] = request.env["ir.fields.converter"].sudo().to_record(
                    request.env["tmf.party.interaction"], "status_change_date", vals["status_change_date"]
                )

            ext = data.get("externalIdentifier")
            if ext is None:
                ext = []                      # safest: absent or empty array
            elif isinstance(ext, dict):
                ext = [ext]                   # CTK expects array
            elif not isinstance(ext, list):
                ext = []                      # fallback

            vals["external_identifier"] = ext

            raw_status = data.get("status")
            vals["status"] = None if raw_status in (None, "") else str(raw_status)


            rec = request.env["tmf.party.interaction"].sudo().create(vals)
            payload = rec.to_tmf_json(host_url=request.httprequest.host_url)

            # MUST be 201 :contentReference[oaicite:2]{index=2}
            return request.make_response(
                json.dumps(payload),
                headers=[("Content-Type", "application/json")],
                status=201,
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=400,
            )

    @http.route(f"{API_BASE}/{RESOURCE}/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_resource(self, rid, **params):
        rec = request.env["tmf.party.interaction"].sudo().search([("tmf_id", "=", rid)], limit=1)
        if not rec:
            return request.make_response("", status=404)
        rec.unlink()
        return request.make_response("", status=204)
