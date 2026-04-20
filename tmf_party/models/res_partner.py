import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

TMF_BASE = "/tmf-api/partyManagement/v5"


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ['res.partner', 'tmf.model.mixin']

    # TMF632 Party (Individual fields)
    tmf_given_name = fields.Char(string="givenName")
    tmf_family_name = fields.Char(string="familyName")

    # Common TMF status (examples in user guide include initialized/validated)
    tmf_managed = fields.Boolean(string="TMF Managed Party", default=False, index=True)

    # Document / identity key (used to link Party/Customer to a stable CRM contact)
    tmf_document_type = fields.Char(string="Document Type", index=True)
    tmf_document_number = fields.Char(string="Document Number", index=True)

    tmf_status = fields.Selection([
        ('initialized', 'Initialized'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string="TMF Status", default='initialized')

    def _notify_tmf_party(self, action, payloads=None):
        if payloads is None:
            managed = self.filtered(lambda r: r.tmf_managed)
            if not managed:
                return
        else:
            managed = self.env["res.partner"]  # empty; payloads already captured
        hub = self.env["tmf.hub.subscription"].sudo()
        kind_map = {
            ("individual", "create"): "IndividualCreateEvent",
            ("individual", "update"): "IndividualAttributeValueChangeEvent",
            ("individual", "state_change"): "IndividualStateChangeEvent",
            ("individual", "delete"): "IndividualDeleteEvent",
            ("organization", "create"): "OrganizationCreateEvent",
            ("organization", "update"): "OrganizationAttributeValueChangeEvent",
            ("organization", "state_change"): "OrganizationStateChangeEvent",
            ("organization", "delete"): "OrganizationDeleteEvent",
        }
        if payloads is None:
            payloads = [(rec._tmf_party_kind(), rec.to_tmf_json()) for rec in managed]
        for kind, payload in payloads:
            event_name = kind_map.get((kind, action))
            if not event_name:
                continue
            try:
                hub._notify_subscribers(kind, event_name, payload)
                hub._notify_subscribers("party", event_name, payload)
            except Exception:
                _logger.exception("TMF632 hub notification failed: event=%s kind=%s", event_name, kind)
                continue

    def _tmf_public_status(self):
        """Return a CTK/schema-safe status value."""
        self.ensure_one()
        # CTK schema rejects 'active' in v5 tests; map any non-supported to 'validated'/'initialized'.
        if self.tmf_status == 'validated':
            return 'validated'
        if self.tmf_status == 'closed':
            return 'closed'
        # treat 'active' and unknown as initialized/validated
        if self.tmf_status == 'active':
            return 'validated'
        return 'initialized'

    def _tmf_party_kind(self):
        self.ensure_one()
        return 'organization' if self.is_company else 'individual'

    def _tmf_href(self):
        self.ensure_one()
        kind = self._tmf_party_kind()
        tmf_id = self.tmf_id or str(self.id)
        return f"{TMF_BASE}/{kind}/{tmf_id}"

    def to_tmf_json(self):
        self.ensure_one()
        kind = self._tmf_party_kind()
        tmf_id = self.tmf_id or str(self.id)

        if kind == 'individual':
            payload = {
                "id": tmf_id,
                "href": self._tmf_href(),
                "@type": "Individual",
                "givenName": self.tmf_given_name or "",
                "familyName": self.tmf_family_name or "",
                "status": self.tmf_status or "initialized",
            }
        else:
            payload = {
                "id": tmf_id,
                "href": self._tmf_href(),
                "@type": "Organization",
                "name": self.name or "",
                "status": self.tmf_status or "initialized",
            }

        return payload

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._notify_tmf_party("create")
        return recs

    def write(self, vals):
        old_status = {rec.id: rec.tmf_status for rec in self}
        res = super().write(vals)
        self._notify_tmf_party("update")
        if "tmf_status" in vals:
            changed = self.filtered(lambda r: old_status.get(r.id) != r.tmf_status)
            if changed:
                changed._notify_tmf_party("state_change")
        return res

    def unlink(self):
        existing = self.exists()
        if not existing:
            return True
        managed = existing.filtered(lambda r: r.tmf_managed)
        payloads = [(rec._tmf_party_kind(), rec.to_tmf_json()) for rec in managed]
        res = super(ResPartner, existing).unlink()
        if payloads:
            self._notify_tmf_party("delete", payloads=payloads)
        return res
