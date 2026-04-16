# -*- coding: utf-8 -*-
from odoo import api, models


class TMFC014WiringTools(models.AbstractModel):
    _name = "tmfc014.wiring.tools"
    _description = "TMFC014 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        sid = str(tmf_id)
        GA = self.env["tmf.geographic.address"].sudo()
        GS = self.env["tmf.geographic.site"].sudo()
        ga_hits = GA.search([("tmfc014_related_party_json", "ilike", sid)])
        if ga_hits:
            ga_hits._tmfc014_resolve_refs()
        gs_hits = GS.search([("related_party_json", "ilike", sid)])
        if gs_hits:
            gs_hits._tmfc014_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)
