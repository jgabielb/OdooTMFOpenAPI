# -*- coding: utf-8 -*-
from odoo import api, models


class TMFC040WiringTools(models.AbstractModel):
    _name = "tmfc040.wiring.tools"
    _description = "TMFC040 Wiring Tools"

    @api.model
    def _resolve_usage_references(self, usage_ids=None):
        Usage = self.env["tmf.usage"].sudo()
        recs = Usage.browse(usage_ids) if usage_ids else Usage.search([])
        if recs:
            recs._tmfc040_resolve_refs()
        return True

    @api.model
    def _handle_party_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        Usage = self.env["tmf.usage"].sudo()
        RP = self.env["tmf.usage.related.party"].sudo()
        lines = RP.search([("party_id", "=", str(tmf_id))])
        affected = Usage.browse(lines.mapped("usage_id").ids)
        if affected:
            affected._tmfc040_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_billing_account_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        Usage = self.env["tmf.usage"].sudo()
        RP = self.env["tmf.usage.related.party"].sudo()
        lines = RP.search([("party_id", "=", str(tmf_id))])
        affected = Usage.browse(lines.mapped("usage_id").ids)
        if affected:
            affected._tmfc040_resolve_refs()
        return True
