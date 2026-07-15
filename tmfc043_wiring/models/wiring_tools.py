# -*- coding: utf-8 -*-
from odoo import api, models


class TMFC043WiringTools(models.AbstractModel):
    _name = "tmfc043.wiring.tools"
    _description = "TMFC043 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        TT = self.env["tmf.trouble.ticket"].sudo()
        SP = self.env["tmf.service.problem"].sudo()
        affected_tt = TT.search([("partner_id.tmf_id", "=", str(tmf_id))])
        if affected_tt:
            affected_tt._tmfc043_resolve_refs()
        affected_sp = SP.search([("originator_party_json", "ilike", str(tmf_id))])
        if affected_sp:
            affected_sp._tmfc043_resolve_refs()
        return True

    @api.model
    def _handle_service_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        TT = self.env["tmf.trouble.ticket"].sudo()
        SP = self.env["tmf.service.problem"].sudo()
        Alarm = self.env["tmf.alarm"].sudo()
        affected_tt = TT.search([("service_id.tmf_id", "=", str(tmf_id))])
        if affected_tt:
            affected_tt._tmfc043_resolve_refs()
        affected_sp = SP.search([("affected_service_json", "ilike", str(tmf_id))])
        if affected_sp:
            affected_sp._tmfc043_resolve_refs()
        affected_alarm = Alarm.search([])
        hits = affected_alarm.filtered(
            lambda a: isinstance(a.affected_service, list)
            and any(isinstance(x, dict) and str(x.get("id") or "") == str(tmf_id) for x in a.affected_service)
        )
        if hits:
            hits._tmfc043_resolve_refs()
        return True

    @api.model
    def _handle_resource_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        SP = self.env["tmf.service.problem"].sudo()
        affected = SP.search([("affected_resource_json", "ilike", str(tmf_id))])
        if affected:
            affected._tmfc043_resolve_refs()
        return True

    def _extract_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        event = payload.get("event")
        if isinstance(event, dict):
            if isinstance(event.get("resource"), dict):
                return event["resource"]
            for v in event.values():
                if isinstance(v, dict) and v.get("id"):
                    return v
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    def _sync_state(self, model_name, payload, fields_to_try=("state", "status")):
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if not ref_id:
            return False
        rec = self.env[model_name].sudo().search([("tmf_id", "=", ref_id)], limit=1)
        if not rec:
            return False
        state = resource.get("state") or resource.get("status")
        if state:
            for field in fields_to_try:
                if field in rec._fields:
                    try:
                        rec.with_context(skip_tmf_wiring=True).write({field: state})
                    except Exception:
                        pass
                    break
        return True

    @api.model
    def _handle_alarm_event(self, payload):
        """TMF642 alarm family (incl. ack/clear/group tasks): sync alarm state."""
        return self._sync_state("tmf.alarm", payload)

    @api.model
    def _handle_service_problem_event(self, payload):
        """TMF656 serviceProblem family: sync problem state + refresh refs."""
        self._sync_state("tmf.service.problem", payload)
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if ref_id:
            SP = self.env["tmf.service.problem"].sudo()
            affected = SP.search([("tmf_id", "=", ref_id)])
            if affected:
                affected._tmfc043_resolve_refs()
        return True

    @api.model
    def _handle_trouble_ticket_event(self, payload):
        """TMF621 troubleTicket family: sync ticket status + refresh refs."""
        self._sync_state("tmf.trouble.ticket", payload)
        resource = self._extract_resource(payload)
        ref_id = str((resource or {}).get("id") or "").strip()
        if ref_id:
            TT = self.env["tmf.trouble.ticket"].sudo()
            affected = TT.search([("tmf_id", "=", ref_id)])
            if affected:
                affected._tmfc043_resolve_refs()
        return True
