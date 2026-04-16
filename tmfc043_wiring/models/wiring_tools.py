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
