# -*- coding: utf-8 -*-
from odoo import api, models


class TMFC039WiringTools(models.AbstractModel):
    _name = "tmfc039.wiring.tools"
    _description = "TMFC039 Wiring Tools"

    @api.model
    def _resolve_agreement_references(self, agreement_ids=None):
        Agreement = self.env["tmf.agreement"].sudo()
        recs = Agreement.browse(agreement_ids) if agreement_ids else Agreement.search([])
        if recs:
            recs._tmfc039_resolve_refs()
        return True

    @api.model
    def _handle_party_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        Agreement = self.env["tmf.agreement"].sudo()
        affected = Agreement.search([("engaged_party", "ilike", str(tmf_id))])
        if affected:
            affected._tmfc039_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_product_specification_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        Agreement = self.env["tmf.agreement"].sudo()
        affected = Agreement.search([("agreement_item", "ilike", str(tmf_id))])
        if affected:
            affected._tmfc039_resolve_refs()
        return True
