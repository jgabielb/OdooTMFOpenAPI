# -*- coding: utf-8 -*-
from odoo import api, models


class TMFC009WiringTools(models.AbstractModel):
    _name = "tmfc009.wiring.tools"
    _description = "TMFC009 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        SQ = self.env["tmf.service.qualification"].sudo()
        affected = SQ.search([("related_party_json", "ilike", str(tmf_id))])
        if affected:
            affected._tmfc009_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_service_specification_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        SQ = self.env["tmf.service.qualification"].sudo()
        affected = SQ.search([("service_qualification_item_json", "ilike", str(tmf_id))])
        if affected:
            affected._tmfc009_resolve_refs()
        return True
