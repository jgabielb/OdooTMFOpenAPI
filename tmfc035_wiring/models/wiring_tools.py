# -*- coding: utf-8 -*-
from odoo import api, models


class TMFC035WiringTools(models.AbstractModel):
    _name = "tmfc035.wiring.tools"
    _description = "TMFC035 Wiring Tools"

    @api.model
    def _handle_party_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        sid = str(tmf_id)
        Perm = self.env["tmf672.permission"].sudo()
        affected = Perm.search([
            "|",
            ("user_json", "ilike", sid),
            ("granter_json", "ilike", sid),
        ])
        if affected:
            affected._tmfc035_resolve_refs()
        return True

    @api.model
    def _handle_party_role_event(self, payload):
        tmf_id = (payload or {}).get("id")
        if not tmf_id:
            return False
        sid = str(tmf_id)
        Perm = self.env["tmf672.permission"].sudo()
        affected_perms = Perm.search([
            "|",
            ("user_json", "ilike", sid),
            ("granter_json", "ilike", sid),
        ])
        if affected_perms:
            affected_perms._tmfc035_resolve_refs()
        UserRole = self.env["tmf672.user.role"].sudo()
        name = (payload or {}).get("name")
        if name:
            affected_ur = UserRole.search([("involvement_role", "=", name)])
            if affected_ur:
                affected_ur._tmfc035_resolve_refs()
        return True

    @api.model
    def _handle_process_flow_event(self, payload):
        """TMF701 processFlow/taskFlow events: sync local flow state by tmf_id."""
        resource = payload or {}
        event = resource.get("event")
        if isinstance(event, dict):
            for value in event.values():
                if isinstance(value, dict) and value.get("id"):
                    resource = value
                    break
        ref_id = str(resource.get("id") or "").strip()
        state = resource.get("state")
        if not ref_id or not state:
            return False
        for model in ("tmf.process.flow", "tmf.task.flow"):
            rec = self.env[model].sudo().search([("tmf_id", "=", ref_id)], limit=1)
            if rec:
                try:
                    rec.with_context(skip_tmf_wiring=True).write({"state": state})
                except Exception:
                    pass
                break
        return True
