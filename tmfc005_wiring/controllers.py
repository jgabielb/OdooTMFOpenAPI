import json

from odoo import http
from odoo.http import request

from .models.wiring import TMFC005_LISTENER_EVENTS


API_BASE = "/tmf-api/productInventoryManagement/v5"


class TMFC005InventoryListenerController(http.Controller):
    def _parse_json(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _json(self, payload=None, status=201):
        body = json.dumps(payload or {})
        return request.make_response(body, status=status, headers=[("Content-Type", "application/json")])

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_listener(self, **_params):
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json({"error": "Missing mandatory attribute: callback"}, status=400)
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc005-product-inventory-{callback}",
            "api_name": "product",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": "any",
            "content_type": "application/json",
        })
        return self._json({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}, status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_listener(self, sid, **_params):
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid)) if str(sid).isdigit() else None
        if not rec or not rec.exists() or rec.api_name != "product":
            return self._json({"error": f"Hub subscription {sid} not found"}, status=404)
        rec.unlink()
        return request.make_response("", status=204)

    @http.route(f"{API_BASE}/listener/<string:event_name>", type="http", auth="public", methods=["POST"], csrf=False)
    def listener(self, event_name, **_params):
        if event_name not in TMFC005_LISTENER_EVENTS:
            return self._json({"error": f"Listener {event_name} not found"}, status=404)
        payload = self._parse_json()
        request.env["tmfc005.wiring.tools"].sudo().handle_event(event_name, payload)
        return self._json({}, status=201)
