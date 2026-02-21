# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import json
import uuid

# TMF681 Communication Management API (Conformance Profile v4.0.0)
API_BASE = "/tmf-api/communicationManagement/v4"
RESOURCE = "communicationMessage"
MODEL = "tmf.communication.message"

# Always include identifiers. Conformance says id/href are mandatory in responses.
ALWAYS_INCLUDE = {"id", "href", "@type"}


def _json_response(payload, status=200, headers=None):
    body = json.dumps(payload, ensure_ascii=False)
    headers = headers or []
    headers.append(("Content-Type", "application/json; charset=utf-8"))
    return request.make_response(body, headers=headers, status=status)


def _get_fields_param():
    return (request.httprequest.args.get("fields") or "").strip()


def _apply_fields_filter(payload, fields_param):
    """
    TMF681 conformance: attribute selection must be supported for first-level attributes.
    Filter ONLY top-level keys. Always keep id/href/@type.
    """
    if not fields_param:
        return payload
    allowed = {f.strip() for f in fields_param.split(",") if f.strip()}
    allowed |= ALWAYS_INCLUDE
    return {k: v for (k, v) in payload.items() if k in allowed}


def _try_parse_json(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return val
        try:
            return json.loads(s)
        except Exception:
            return val
    return val


def _record_to_payload(rec):
    """
    Use model to_tmf_json() and normalize a couple of fields if stored as strings.
    """
    base = rec.to_tmf_json()

    if not base.get("@type"):
        base["@type"] = "CommunicationMessage"

    base["receiver"] = _try_parse_json(base.get("receiver"))
    base["sender"] = _try_parse_json(base.get("sender"))
    base["characteristic"] = _try_parse_json(base.get("characteristic"))
    base["attachment"] = _try_parse_json(base.get("attachment"))

    if base.get("receiver") is not None and not isinstance(base["receiver"], list):
        base["receiver"] = [base["receiver"]]

    return base


def _build_href(host_url, tmf_id):
    host_url = (host_url or "").rstrip("/")
    return f"{host_url}{API_BASE}/{RESOURCE}/{tmf_id}"


def _domain_from_query(args):
    domain = []
    if args.get("messageType"):
        domain.append(("message_type", "=", args.get("messageType")))
    if args.get("state"):
        domain.append(("state", "=", args.get("state")))
    if args.get("subject"):
        domain.append(("subject", "=", args.get("subject")))
    if args.get("priority"):
        domain.append(("priority", "=", args.get("priority")))
    return domain


class TMF681CommunicationMessageController(http.Controller):

    @http.route(
        f"{API_BASE}/{RESOURCE}",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def list_communication_message(self, **kwargs):
        fields_param = _get_fields_param()
        domain = _domain_from_query(request.httprequest.args)

        recs = request.env[MODEL].sudo().search(domain)
        items = []
        for r in recs:
            payload = _record_to_payload(r)
            payload = _apply_fields_filter(payload, fields_param)
            items.append(payload)

        return _json_response(items, status=200)

    @http.route(
        f"{API_BASE}/{RESOURCE}/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_communication_message(self, tmf_id, **kwargs):
        fields_param = _get_fields_param()

        rec = request.env[MODEL].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)

        payload = _record_to_payload(rec)
        payload = _apply_fields_filter(payload, fields_param)
        return _json_response(payload, status=200)

    @http.route(
        f"{API_BASE}/{RESOURCE}",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_communication_message(self, **kwargs):
        try:
            raw = request.httprequest.data.decode("utf-8") if request.httprequest.data else "{}"
            payload_in = json.loads(raw or "{}")
        except Exception:
            return _json_response({"error": "Invalid JSON"}, status=400)

        # Mandatory fields
        content = payload_in.get("content")
        message_type = payload_in.get("messageType")
        receiver = payload_in.get("receiver")
        sender = payload_in.get("sender")

        if not content or not message_type or receiver is None or sender is None:
            return _json_response(
                {"error": "Missing mandatory attributes",
                 "mandatory": ["content", "messageType", "receiver", "sender"]},
                status=400,
            )

        # receiver must be a non-empty array (wrap dict -> [dict])
        if isinstance(receiver, dict):
            receiver = [receiver]
        if not isinstance(receiver, list) or len(receiver) == 0:
            return _json_response({"error": "receiver must be a non-empty array"}, status=400)

        # sender must be a non-empty object
        if not isinstance(sender, dict) or not sender:
            return _json_response({"error": "sender must be a non-empty object"}, status=400)

        host_url = request.httprequest.host_url
        new_id = payload_in.get("id") or str(uuid.uuid4())
        href = payload_in.get("href") or _build_href(host_url, new_id)

        vals = {}
        model_fields = request.env[MODEL]._fields

        if "tmf_id" in model_fields:
            vals["tmf_id"] = new_id
        if "href" in model_fields:
            vals["href"] = href

        # IMPORTANT: if your model uses fields.Json, store Python list/dict (NO json.dumps)
        vals.update({
            "content": content,
            "message_type": message_type,
            "receiver": receiver,
            "sender": sender,
        })

        # Optional passthroughs
        if "subject" in model_fields and "subject" in payload_in:
            vals["subject"] = payload_in.get("subject")
        if "state" in model_fields and "state" in payload_in:
            vals["state"] = payload_in.get("state")
        if "priority" in model_fields and "priority" in payload_in:
            vals["priority"] = payload_in.get("priority")
        if "description" in model_fields and "description" in payload_in:
            vals["description"] = payload_in.get("description")
        if "log_flag" in model_fields and "logFlag" in payload_in:
            vals["log_flag"] = bool(payload_in.get("logFlag"))

        if "characteristic" in model_fields and "characteristic" in payload_in:
            vals["characteristic"] = payload_in.get("characteristic") or []

        if "attachment" in model_fields and "attachment" in payload_in:
            vals["attachment"] = payload_in.get("attachment") or []

        try:
            rec = request.env[MODEL].sudo().create(vals)
        except ValidationError as e:
            return _json_response({"error": str(e)}, status=400)
        except Exception:
            return _json_response({"error": "Failed to create"}, status=500)

        out = _record_to_payload(rec)
        return _json_response(out, status=201)

    @http.route(
        f"{API_BASE}/{RESOURCE}/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["PATCH"],
        csrf=False,
    )
    def patch_communication_message(self, tmf_id, **kwargs):
        rec = request.env[MODEL].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)

        try:
            raw = request.httprequest.data.decode("utf-8") if request.httprequest.data else "{}"
            payload_in = json.loads(raw or "{}")
        except Exception:
            return _json_response({"error": "Invalid JSON"}, status=400)

        vals = {}
        mf = request.env[MODEL]._fields

        if "content" in payload_in and "content" in mf:
            vals["content"] = payload_in.get("content")
        if "description" in payload_in and "description" in mf:
            vals["description"] = payload_in.get("description")
        if "logFlag" in payload_in and "log_flag" in mf:
            vals["log_flag"] = bool(payload_in.get("logFlag"))
        if "messageType" in payload_in and "message_type" in mf:
            vals["message_type"] = payload_in.get("messageType")
        if "priority" in payload_in and "priority" in mf:
            vals["priority"] = payload_in.get("priority")
        if "state" in payload_in and "state" in mf:
            vals["state"] = payload_in.get("state")
        if "subject" in payload_in and "subject" in mf:
            vals["subject"] = payload_in.get("subject")
        if "tryTimes" in payload_in and "try_times" in mf:
            vals["try_times"] = payload_in.get("tryTimes")

        if "receiver" in payload_in and "receiver" in mf:
            receiver = payload_in.get("receiver")
            if isinstance(receiver, dict):
                receiver = [receiver]
            if not isinstance(receiver, list) or len(receiver) == 0:
                return _json_response({"error": "receiver must be a non-empty array"}, status=400)
            vals["receiver"] = receiver

        if "sender" in payload_in and "sender" in mf:
            sender = payload_in.get("sender")
            if not isinstance(sender, dict) or not sender:
                return _json_response({"error": "sender must be a non-empty object"}, status=400)
            vals["sender"] = sender

        if "characteristic" in payload_in and "characteristic" in mf:
            vals["characteristic"] = payload_in.get("characteristic") or []

        if "attachment" in payload_in and "attachment" in mf:
            vals["attachment"] = payload_in.get("attachment") or []

        if vals:
            rec.write(vals)

        out = _record_to_payload(rec)
        return _json_response(out, status=200)

    @http.route(
        f"{API_BASE}/hub",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def hub_register(self, **kwargs):
        try:
            raw = request.httprequest.data.decode("utf-8") if request.httprequest.data else "{}"
            payload_in = json.loads(raw or "{}")
        except Exception:
            return _json_response({"error": "Invalid JSON"}, status=400)

        hub_id = str(uuid.uuid4())
        host_url = request.httprequest.host_url.rstrip("/")
        resp = {
            "id": hub_id,
            "callback": payload_in.get("callback"),
            "query": payload_in.get("query"),
            "href": f"{host_url}{API_BASE}/hub/{hub_id}",
        }
        return _json_response(resp, status=201)

    @http.route(
        f"{API_BASE}/hub/<string:hub_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def hub_unregister(self, hub_id, **kwargs):
        return request.make_response("", status=204)

    @http.route(
        f"{API_BASE}/listener/communicationMessageAttributeValueChangeEvent",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_attr_change(self, **kwargs):
        return request.make_response("", status=204)

    @http.route(
        f"{API_BASE}/listener/communicationMessageStateChangeEvent",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def listener_state_change(self, **kwargs):
        return request.make_response("", status=204)

    @http.route(
        f"{API_BASE}/{RESOURCE}/<string:tmf_id>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def delete_communication_message(self, tmf_id, **kwargs):
        rec = request.env[MODEL].sudo().search([("tmf_id", "=", tmf_id)], limit=1)
        if not rec:
            return _json_response({"error": "Not found"}, status=404)

        try:
            rec.unlink()
        except Exception:
            return _json_response({"error": "Failed to delete"}, status=500)

        return request.make_response("", status=204)
