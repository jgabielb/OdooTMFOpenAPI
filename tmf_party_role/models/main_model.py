# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json


class TMFPartyRole(models.Model):
    _name = "tmf.party.role"
    _description = "TMF669 PartyRole"
    _inherit = ["tmf.model.mixin"]

    # TMF top-level fields
    type_name = fields.Char(string="@type", required=True, default="PartyRole")
    name = fields.Char(string="name", required=True)
    role = fields.Char(string="role")
    status = fields.Char(string="status")
    status_reason = fields.Char(string="statusReason")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")

    # Store complex substructures as JSON (string) to keep controller simple & CTK-friendly
    engaged_party_json = fields.Text(string="engagedParty", required=True)
    party_role_spec_json = fields.Text(string="partyRoleSpecification")
    account_json = fields.Text(string="account")
    agreement_json = fields.Text(string="agreement")
    characteristic_json = fields.Text(string="characteristic")
    contact_medium_json = fields.Text(string="contactMedium")
    credit_profile_json = fields.Text(string="creditProfile")
    payment_method_json = fields.Text(string="paymentMethod")
    related_party_json = fields.Text(string="relatedParty")
    valid_for_json = fields.Text(string="validFor")

    def _resolve_partner_from_payload(self):
        self.ensure_one()
        party = self._loads(self.engaged_party_json)
        if not isinstance(party, dict):
            return self.env["res.partner"]

        pid = party.get("id")
        pname = party.get("name")
        Partner = self.env["res.partner"].sudo()

        if pid:
            partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
            if not partner and str(pid).isdigit():
                partner = Partner.browse(int(pid))
            if partner and partner.exists():
                return partner

        if pname:
            partner = Partner.search([("name", "=", pname)], limit=1)
            if partner:
                return partner

        return self.env["res.partner"]

    def _sync_partner_link(self):
        for rec in self:
            if rec.partner_id and rec.partner_id.exists():
                continue
            partner = rec._resolve_partner_from_payload()
            if partner and partner.exists():
                rec.partner_id = partner.id

    def _get_tmf_api_path(self):
        # Base resource path must be /partyRole in this API. :contentReference[oaicite:9]{index=9}
        return "/partyRoleManagement/v5/partyRole"

    def _loads(self, txt):
        if not txt:
            return None
        try:
            return json.loads(txt)
        except Exception:
            return None

    def _none_if_false(v):
        return None if v is False else v
    
    def _none_if_false(self, value):
        # Odoo Char fields return False when empty → CTK expects string or absence
        return None if value is False else value

    def to_tmf_json(self):
        self.ensure_one()

        obj = {
            "@type": self.type_name or "PartyRole",
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,

            # optional scalar fields → never return False
            "role": self._none_if_false(self.role),
            "status": self._none_if_false(self.status),
            "statusReason": self._none_if_false(self.status_reason),

            # structured fields
            "engagedParty": self._loads(self.engaged_party_json),
            "partyRoleSpecification": self._loads(self.party_role_spec_json),
            "account": self._loads(self.account_json),
            "agreement": self._loads(self.agreement_json),
            "characteristic": self._loads(self.characteristic_json),
            "contactMedium": self._loads(self.contact_medium_json),
            "creditProfile": self._loads(self.credit_profile_json),
            "paymentMethod": self._loads(self.payment_method_json),
            "relatedParty": self._loads(self.related_party_json),
            "validFor": self._loads(self.valid_for_json),
        }

        # remove only None values (never False)
        return {k: v for k, v in obj.items() if v is not None}


    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_partner_link()
        for rec in recs:
            self._notify("partyRole", "create", rec)
        return recs

    def write(self, vals):
        status_before = {rec.id: rec.status for rec in self}
        res = super().write(vals)
        if "engaged_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        for rec in self:
            self._notify("partyRole", "update", rec)
            if "status" in vals and status_before.get(rec.id) != rec.status:
                self._notify("partyRole", "state_change", rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="partyRole",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
