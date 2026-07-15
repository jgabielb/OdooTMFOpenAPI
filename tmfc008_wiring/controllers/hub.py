# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request


class TMFC008HubController(http.Controller):
    """Hub-registration façade for TMFC008 backed by ``tmf.hub.subscription``."""

    def _parse(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _resp(self, p=None, status=201):
        return request.make_response(json.dumps(p or {}), status=status,
                                     headers=[("Content-Type", "application/json")])

    @http.route(["/tmfc008/hub/serviceInventory"],
                type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def register_hub(self):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("name", "like", "tmfc008-")])
            return self._resp([{"id": str(s.id), "name": s.name, "callback": s.callback,
                                "query": s.query or "", "api_name": s.api_name}
                               for s in subs], status=200)
        data = self._parse()
        cb = data.get("callback")
        if not cb:
            return self._resp({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "service"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc008-{api_name}-{cb}", "api_name": api_name, "callback": cb,
            "query": data.get("query", ""), "event_type": data.get("event_type") or "any",
            "content_type": "application/json",
        })
        return self._resp({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""}, status=201)

    @http.route(["/tmfc008/hub/serviceInventory/<string:sid>"],
                type="http", auth="none", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc008-"):
                rec = None
        if not rec:
            return self._resp({"error": f"Hub subscription {sid} not found"}, status=404)
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._resp({"id": str(rec.id), "name": rec.name, "callback": rec.callback,
                           "query": rec.query or "", "api_name": rec.api_name}, status=200)
