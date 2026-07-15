# -*- coding: utf-8 -*-
"""TMFC001 ProductCatalogManagement — ODA listener + hub façade.

Subscribed events per TMFC001 YAML:
- TMF633 serviceSpecification / resourceSpecification create/change/delete
- TMF632 individual/organization delete
- TMF669 partyRole delete
Additive (dependent-API robustness, not YAML-mandated):
- TMF662 entitySpecification create/change/delete
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

BASE_L = "/tmfc001/listener"
BASE_H = "/tmfc001/hub"
# Legacy paths kept for wire compatibility with subscriptions registered before
# the listeners moved out of tmf_product_catalog.
LEGACY = "/tmf-api/productCatalogManagement/v5/listener"

SERVICE_SPEC_EVENTS = {
    "ServiceSpecificationCreateEvent", "ServiceSpecificationChangeEvent",
    "ServiceSpecificationAttributeValueChangeEvent",
    "ServiceSpecificationStateChangeEvent", "ServiceSpecificationDeleteEvent",
}
RESOURCE_SPEC_EVENTS = {
    "ResourceSpecificationCreateEvent", "ResourceSpecificationChangeEvent",
    "ResourceSpecificationAttributeValueChangeEvent",
    "ResourceSpecificationStateChangeEvent", "ResourceSpecificationDeleteEvent",
}
ENTITY_SPEC_EVENTS = {
    "EntitySpecificationCreateEvent", "EntitySpecificationChangeEvent",
    "EntitySpecificationAttributeValueChangeEvent",
    "EntitySpecificationStateChangeEvent", "EntitySpecificationDeleteEvent",
}
PARTY_EVENTS = {
    "IndividualDeleteEvent", "OrganizationDeleteEvent", "PartyDeleteEvent",
}
PARTY_ROLE_EVENTS = {"PartyRoleDeleteEvent"}


class TMFC001ListenerController(http.Controller):
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

    def _dispatch(self, payload, allowed, handler):
        ev = str((payload or {}).get("eventType") or "").strip() if isinstance(payload, dict) else ""
        if not ev:
            return self._resp({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in allowed:
            return self._resp({"error": f"Listener event '{ev}' not supported"}, status=404)
        try:
            getattr(request.env["tmfc001.wiring.tools"].sudo(), handler)(payload)
        except Exception as exc:
            _logger.exception("TMFC001 listener %s failed", handler)
            return self._resp({"error": str(exc)}, status=400)
        return self._resp({}, status=201)

    def _apply(self, handler):
        """Legacy per-event routes: no eventType gate (old senders may omit it)."""
        payload = self._parse()
        if not isinstance(payload, dict) or not payload:
            return self._resp({"error": "Invalid JSON body"}, status=400)
        try:
            getattr(request.env["tmfc001.wiring.tools"].sudo(), handler)(payload)
        except Exception as exc:
            _logger.exception("TMFC001 listener %s failed", handler)
            return self._resp({"error": str(exc)}, status=400)
        return self._resp({}, status=201)

    # ------------------------------------------------------------------
    # Listener routes (one per subscribed source)
    # ------------------------------------------------------------------

    @http.route(f"{BASE_L}/serviceSpecification", type="http", auth="public",
                methods=["POST"], csrf=False)
    def l_service_spec(self, **_p):
        return self._dispatch(self._parse(), SERVICE_SPEC_EVENTS,
                              "_reconcile_service_specification_refs")

    @http.route(f"{BASE_L}/resourceSpecification", type="http", auth="public",
                methods=["POST"], csrf=False)
    def l_resource_spec(self, **_p):
        return self._dispatch(self._parse(), RESOURCE_SPEC_EVENTS,
                              "_reconcile_resource_specification_refs")

    @http.route(f"{BASE_L}/entitySpecification", type="http", auth="public",
                methods=["POST"], csrf=False)
    def l_entity_spec(self, **_p):
        return self._dispatch(self._parse(), ENTITY_SPEC_EVENTS,
                              "_reconcile_entity_specification_refs")

    @http.route(f"{BASE_L}/party", type="http", auth="public",
                methods=["POST"], csrf=False)
    def l_party(self, **_p):
        return self._dispatch(self._parse(), PARTY_EVENTS, "_reconcile_related_party_refs")

    @http.route(f"{BASE_L}/partyRole", type="http", auth="public",
                methods=["POST"], csrf=False)
    def l_party_role(self, **_p):
        return self._dispatch(self._parse(), PARTY_ROLE_EVENTS, "_reconcile_party_role_refs")

    # ------------------------------------------------------------------
    # Legacy per-event aliases (previously hosted by tmf_product_catalog)
    # ------------------------------------------------------------------

    @http.route([f"{LEGACY}/serviceSpecificationCreateEvent",
                 f"{LEGACY}/serviceSpecificationAttributeValueChangeEvent",
                 f"{LEGACY}/serviceSpecificationStateChangeEvent",
                 f"{LEGACY}/serviceSpecificationDeleteEvent"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def legacy_service_spec(self, **_p):
        return self._apply("_reconcile_service_specification_refs")

    @http.route([f"{LEGACY}/resourceSpecificationCreateEvent",
                 f"{LEGACY}/resourceSpecificationChangeEvent",
                 f"{LEGACY}/resourceSpecificationDeleteEvent"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def legacy_resource_spec(self, **_p):
        return self._apply("_reconcile_resource_specification_refs")

    @http.route([f"{LEGACY}/individualDeleteEvent",
                 f"{LEGACY}/organizationDeleteEvent"],
                type="http", auth="public", methods=["POST"], csrf=False)
    def legacy_party_delete(self, **_p):
        return self._apply("_reconcile_related_party_refs")

    @http.route(f"{LEGACY}/partyRoleDeleteEvent",
                type="http", auth="public", methods=["POST"], csrf=False)
    def legacy_party_role_delete(self, **_p):
        return self._apply("_reconcile_party_role_refs")

    # ------------------------------------------------------------------
    # Hub façade
    # ------------------------------------------------------------------

    @http.route(BASE_H, type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("name", "like", "tmfc001-")])
            return self._resp([{"id": str(s.id), "name": s.name, "callback": s.callback,
                                "query": s.query or "", "api_name": s.api_name}
                               for s in subs], status=200)
        data = self._parse()
        cb = data.get("callback")
        if not cb:
            return self._resp({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "productOffering"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc001-{api_name}-{cb}", "api_name": api_name, "callback": cb,
            "query": data.get("query", ""), "event_type": data.get("event_type") or "any",
            "content_type": "application/json",
        })
        return self._resp({"id": str(rec.id), "callback": rec.callback,
                           "query": rec.query or ""}, status=201)

    @http.route(f"{BASE_H}/<string:sid>", type="http", auth="public",
                methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc001-"):
                rec = None
        if not rec:
            return self._resp({"error": f"Hub subscription {sid} not found"}, status=404)
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._resp({"id": str(rec.id), "name": rec.name, "callback": rec.callback,
                           "query": rec.query or "", "api_name": rec.api_name}, status=200)
