# -*- coding: utf-8 -*-
"""TMFC043 FaultManagement listener + hub controller."""

import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

TMFC043_LISTENER_BASE = "/tmfc043/listener"
TMFC043_HUB_BASE = "/tmfc043/hub"

PARTY_EVENTS = {
    "PartyCreateEvent", "PartyAttributeValueChangeEvent",
    "PartyStateChangeEvent", "PartyDeleteEvent",
    "IndividualCreateEvent", "IndividualAttributeValueChangeEvent",
    "IndividualStateChangeEvent", "IndividualDeleteEvent",
    "OrganizationCreateEvent", "OrganizationAttributeValueChangeEvent",
    "OrganizationStateChangeEvent", "OrganizationDeleteEvent",
}
SERVICE_EVENTS = {
    "ServiceCreateEvent", "ServiceAttributeValueChangeEvent",
    "ServiceStateChangeEvent", "ServiceDeleteEvent",
}
RESOURCE_EVENTS = {
    "ResourceCreateEvent", "ResourceAttributeValueChangeEvent",
    "ResourceStateChangeEvent", "ResourceDeleteEvent",
}
PARTY_ROLE_EVENTS = {"PartyRoleDeleteEvent"}
SERVICE_CATALOG_EVENTS = {
    "ServiceCatalogCreateEvent", "ServiceCatalogChangeEvent", "ServiceCatalogDeleteEvent",
    "ServiceCategoryCreateEvent", "ServiceCategoryChangeEvent", "ServiceCategoryDeleteEvent",
    "ServiceCandidateCreateEvent", "ServiceCandidateChangeEvent", "ServiceCandidateDeleteEvent",
    "ServiceSpecificationCreateEvent", "ServiceSpecificationChangeEvent",
    "ServiceSpecificationDeleteEvent",
}
GEO_EVENTS = {
    "GeographicAddressValidationStateChangeEvent",
    "GeographicSiteCreateEvent", "GeographicSiteAttributeValueChangeEvent",
    "GeographicSiteStatusChangeEvent", "GeographicSiteDeleteEvent",
    "GeographicLocationCreateEvent", "GeographicLocationAttributeValueChangeEvent",
    "GeographicLocationDeleteEvent",
}
ALARM_EVENTS = {
    "AlarmCreateEvent", "AlarmAttributeValueChangeEvent",
    "AlarmStateChangeEvent", "AlarmDeleteEvent",
    "AckAlarmsCreateEvent", "AckAlarmsStateChangeEvent",
    "UnAckAlarmsCreateEvent", "UnAckAlarmsStateChangeEvent",
    "ClearAlarmsCreateEvent", "ClearAlarmsStateChangeEvent",
    "CommentAlarmsCreateEvent", "CommentAlarmsStateChangeEvent",
    "GroupAlarmsCreateEvent", "GroupAlarmsStateChangeEvent",
    "UnGroupAlarmsCreateEvent", "UnGroupAlarmsStateChangeEvent",
}
SERVICE_PROBLEM_EVENTS = {
    "ServiceProblemCreateEvent", "ServiceProblemAttributeValueChangeEvent",
    "ServiceProblemStateChangeEvent", "ServiceProblemDeleteEvent",
    "ServiceProblemInformationRequiredEvent",
    "ProblemAcknowledgementCreateEvent", "ProblemAcknowledgementStateChangeEvent",
    "ProblemAcknowledgementDeleteEvent",
    "ProblemGroupCreateEvent", "ProblemGroupStateChangeEvent", "ProblemGroupDeleteEvent",
    "ProblemUnGroupCreateEvent", "ProblemUnGroupStateChangeEvent",
    "ProblemUnGroupDeleteEvent",
}
TROUBLE_TICKET_EVENTS = {
    "TroubleTicketCreateEvent", "TroubleTicketAttributeValueChangeEvent",
    "TroubleTicketStatusChangeEvent", "TroubleTicketStateChangeEvent",
    "TroubleTicketDeleteEvent", "TroubleTicketResolvedEvent",
    "TroubleTicketInformationRequiredEvent",
}
ENTITY_CATALOG_EVENTS = {
    "EntityCatalogCreateEvent", "EntityCatalogDeleteEvent",
    "EntityCatalogItemCreateEvent", "EntityCatalogItemDeleteEvent",
    "EntitySpecificationCreateEvent", "EntitySpecificationDeleteEvent",
    "AssociationSpecificationCreateEvent", "AssociationSpecificationDeleteEvent",
    "AssociationCreateEvent", "AssociationDeleteEvent",
}


class TMFC043ListenerController(http.Controller):

    def _parse_json(self):
        raw = request.httprequest.data or b"{}"
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def _json_response(self, payload=None, status=201):
        return request.make_response(
            json.dumps(payload or {}),
            status=status,
            headers=[("Content-Type", "application/json")],
        )

    def _dispatch(self, payload, allowed, handler_name, source):
        ev = str((payload or {}).get("eventType") or "").strip() if isinstance(payload, dict) else ""
        if not ev:
            return self._json_response({"error": "Missing mandatory attribute: eventType"}, status=400)
        if ev not in allowed:
            return self._json_response({"error": f"Listener event '{ev}' not supported"}, status=404)
        tools = request.env["tmfc043.wiring.tools"].sudo()
        getattr(tools, handler_name)(payload)
        _logger.info("TMFC043: acknowledged %s event %s", source, ev)
        return self._json_response({}, status=201)

    @http.route(f"{TMFC043_LISTENER_BASE}/party",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_party(self, **_p):
        return self._dispatch(self._parse_json(), PARTY_EVENTS, "_handle_party_event", "party")

    @http.route(f"{TMFC043_LISTENER_BASE}/service",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_service(self, **_p):
        return self._dispatch(self._parse_json(), SERVICE_EVENTS, "_handle_service_event", "service")

    @http.route(f"{TMFC043_LISTENER_BASE}/resource",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_resource(self, **_p):
        return self._dispatch(self._parse_json(), RESOURCE_EVENTS, "_handle_resource_event", "resource")

    @http.route(f"{TMFC043_LISTENER_BASE}/partyRole",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_party_role(self, **_p):
        return self._dispatch(self._parse_json(), PARTY_ROLE_EVENTS,
                              "_handle_party_event", "partyRole")

    @http.route(f"{TMFC043_LISTENER_BASE}/serviceCatalog",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_service_catalog(self, **_p):
        return self._dispatch(self._parse_json(), SERVICE_CATALOG_EVENTS,
                              "_handle_service_event", "serviceCatalog")

    @http.route(f"{TMFC043_LISTENER_BASE}/geographic",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_geographic(self, **_p):
        return self._dispatch(self._parse_json(), GEO_EVENTS,
                              "_handle_resource_event", "geographic")

    @http.route(f"{TMFC043_LISTENER_BASE}/alarm",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_alarm(self, **_p):
        return self._dispatch(self._parse_json(), ALARM_EVENTS,
                              "_handle_alarm_event", "alarm")

    @http.route(f"{TMFC043_LISTENER_BASE}/serviceProblem",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_service_problem(self, **_p):
        return self._dispatch(self._parse_json(), SERVICE_PROBLEM_EVENTS,
                              "_handle_service_problem_event", "serviceProblem")

    @http.route(f"{TMFC043_LISTENER_BASE}/troubleTicket",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_trouble_ticket(self, **_p):
        return self._dispatch(self._parse_json(), TROUBLE_TICKET_EVENTS,
                              "_handle_trouble_ticket_event", "troubleTicket")

    @http.route(f"{TMFC043_LISTENER_BASE}/entityCatalog",
                type="http", auth="public", methods=["POST"], csrf=False)
    def listener_entity_catalog(self, **_p):
        return self._dispatch(self._parse_json(), ENTITY_CATALOG_EVENTS,
                              "_handle_service_event", "entityCatalog")

    @http.route(TMFC043_HUB_BASE,
                type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub_register(self, **_p):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("name", "like", "tmfc043-")])
            return self._json_response(
                [{"id": str(s.id), "name": s.name, "callback": s.callback,
                  "query": s.query or "", "api_name": s.api_name} for s in subs],
                status=200,
            )
        data = self._parse_json()
        callback = data.get("callback")
        if not callback:
            return self._json_response({"error": "Missing mandatory attribute: callback"}, status=400)
        api_name = data.get("api_name") or "troubleTicket"
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmfc043-{api_name}-{callback}",
            "api_name": api_name,
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("event_type") or "any",
            "content_type": "application/json",
        })
        return self._json_response(
            {"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""},
            status=201,
        )

    @http.route(f"{TMFC043_HUB_BASE}/<string:sid>",
                type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_p):
        rec = None
        if str(sid).isdigit():
            rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
            if not rec.exists() or not rec.name.startswith("tmfc043-"):
                rec = None
        if not rec:
            return self._json_response({"error": f"Hub subscription {sid} not found"}, status=404)
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json_response(
            {"id": str(rec.id), "name": rec.name, "callback": rec.callback,
             "query": rec.query or "", "api_name": rec.api_name},
            status=200,
        )
