import json
from odoo import http
from odoo.http import request


API_BASE = "/tmf-api/event/v4"


def _json_response(payload, status=200, headers=None):
    base_headers = [("Content-Type", "application/json")]
    if headers:
        base_headers.extend(headers)
    return request.make_response(json.dumps(payload), headers=base_headers, status=status)


def _error(status, reason):
    status_str = str(status)
    return _json_response({"error": {"code": status_str, "status": status_str, "reason": reason}}, status=status)


def _parse_json():
    try:
        raw = request.httprequest.data or b"{}"
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _fields_filter(payload, fields_csv):
    if not fields_csv:
        return payload
    wanted = {item.strip() for item in str(fields_csv).split(",") if item.strip()}
    if not wanted:
        return payload
    wanted |= {"id", "href"}
    return {key: value for key, value in payload.items() if key in wanted}


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


def _subscription_json(rec):
    base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
    href = f"{base_url}{API_BASE}/hub/{rec.id}"
    return {
        "id": str(rec.id),
        "href": href,
        "callback": rec.callback,
        "query": rec.query or "",
        "@type": "Hub",
    }


class TMF688EventController(http.Controller):
    @http.route(f"{API_BASE}/topic", type="http", auth="public", methods=["GET"], csrf=False)
    def list_topic(self, **params):
        domain = []
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.event.topic"].sudo()
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/topic", type="http", auth="public", methods=["POST"], csrf=False)
    def create_topic(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        vals = {
            "name": data.get("name"),
            "content_query": data.get("contentQuery"),
            "header_query": data.get("headerQuery"),
            "extra_json": {
                key: value
                for key, value in data.items()
                if key not in {"name", "contentQuery", "headerQuery", "id", "href"}
            },
        }
        rec = request.env["tmf.event.topic"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(f"{API_BASE}/topic/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_topic(self, rid, **params):
        rec = _find_by_rid("tmf.event.topic", rid)
        if not rec:
            return _error(404, f"Topic {rid} not found")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/topic/<string:rid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_topic(self, rid, **_params):
        rec = _find_by_rid("tmf.event.topic", rid)
        if not rec:
            return _error(404, f"Topic {rid} not found")
        rec.sudo().unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/topic/<string:topic_id>/event", type="http", auth="public", methods=["GET"], csrf=False)
    def list_event(self, topic_id, **params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        model = request.env["tmf.event"].sudo()
        domain = [("topic_id", "=", topic.id)]
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit)
        payload = [_fields_filter(rec.to_tmf_json(), params.get("fields")) for rec in recs]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(total))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/topic/<string:topic_id>/event", type="http", auth="public", methods=["POST"], csrf=False)
    def create_event(self, topic_id, **_params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        vals = {
            "topic_id": topic.id,
            "correlation_id": data.get("correlationId"),
            "description": data.get("description"),
            "domain": data.get("domain"),
            "event_id": data.get("eventId"),
            "event_time": data.get("eventTime"),
            "event_type": data.get("eventType"),
            "priority": data.get("priority"),
            "time_occurred": data.get("timeOccurred") or data.get("timeOcurred"),
            "title": data.get("title"),
            "analytic_characteristic": data.get("analyticCharacteristic") or [],
            "event_payload": data.get("event") or {},
            "related_party": data.get("relatedParty") or [],
            "reporting_system": data.get("reportingSystem") or {},
            "source": data.get("source") or {},
            "extra_json": {
                key: value
                for key, value in data.items()
                if key
                not in {
                    "correlationId",
                    "description",
                    "domain",
                    "eventId",
                    "eventTime",
                    "eventType",
                    "priority",
                    "timeOccurred",
                    "timeOcurred",
                    "title",
                    "analyticCharacteristic",
                    "event",
                    "relatedParty",
                    "reportingSystem",
                    "source",
                    "id",
                    "href",
                }
            },
        }
        rec = request.env["tmf.event"].sudo().create(vals)
        return _json_response(rec.to_tmf_json(), status=201)

    @http.route(
        f"{API_BASE}/topic/<string:topic_id>/event/<string:rid>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_event(self, topic_id, rid, **params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        rec = _find_by_rid("tmf.event", rid)
        if not rec or rec.topic_id.id != topic.id:
            return _error(404, f"Event {rid} not found on topic {topic_id}")
        return _json_response(_fields_filter(rec.to_tmf_json(), params.get("fields")), status=200)

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf688-event-{callback}",
                "api_name": "topic",
                "callback": callback,
                "query": data.get("query", ""),
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "topic":
            return _error(404, f"Hub subscription {sid} not found")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/topic/<string:topic_id>/hub", type="http", auth="public", methods=["GET"], csrf=False)
    def list_hub(self, topic_id, **params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        subs = request.env["tmf.hub.subscription"].sudo().search([("api_name", "=", "event")])
        filtered = [s for s in subs if f"topicId={topic.tmf_id}" in (s.query or "")]
        offset = int(params.get("offset", 0) or 0)
        limit = params.get("limit")
        limit = int(limit) if limit not in (None, "") else None
        sliced = filtered[offset : (offset + limit) if limit is not None else None]
        payload = [_fields_filter(_subscription_json(rec), params.get("fields")) for rec in sliced]
        headers = [("X-Result-Count", str(len(payload))), ("X-Total-Count", str(len(filtered)))]
        return _json_response(payload, status=200, headers=headers)

    @http.route(f"{API_BASE}/topic/<string:topic_id>/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def create_hub(self, topic_id, **_params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        callback = data.get("callback")
        if not callback:
            return _error(400, "Missing mandatory attribute: callback")
        topic_query = f"topicId={topic.tmf_id}"
        query = data.get("query")
        full_query = f"{query}&{topic_query}" if query else topic_query
        rec = request.env["tmf.hub.subscription"].sudo().create(
            {
                "name": f"tmf688-topic-{topic.tmf_id}-{callback}",
                "api_name": "event",
                "callback": callback,
                "query": full_query,
                "event_type": "any",
                "content_type": "application/json",
            }
        )
        return _json_response(_subscription_json(rec), status=201)

    @http.route(
        f"{API_BASE}/topic/<string:topic_id>/hub/<string:sid>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_hub(self, topic_id, sid, **params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "event" or f"topicId={topic.tmf_id}" not in (rec.query or ""):
            return _error(404, f"Hub subscription {sid} not found for topic {topic_id}")
        return _json_response(_fields_filter(_subscription_json(rec), params.get("fields")), status=200)

    @http.route(
        f"{API_BASE}/topic/<string:topic_id>/hub/<string:sid>",
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
    )
    def delete_hub(self, topic_id, sid, **_params):
        topic = _find_by_rid("tmf.event.topic", topic_id)
        if not topic:
            return _error(404, f"Topic {topic_id} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "event" or f"topicId={topic.tmf_id}" not in (rec.query or ""):
            return _error(404, f"Hub subscription {sid} not found for topic {topic_id}")
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/listener/topicCreateEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_topic_create_event(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/topicChangeEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_topic_change_event(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)

    @http.route(f"{API_BASE}/listener/topicDeleteEvent", type="http", auth="public", methods=["POST"], csrf=False)
    def listen_topic_delete_event(self, **_params):
        data = _parse_json()
        if not isinstance(data, dict):
            return _error(400, "Invalid JSON body")
        return request.make_response("", status=201)
