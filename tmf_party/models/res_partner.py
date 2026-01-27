from odoo import models, fields

TMF_BASE = "/tmf-api/partyManagement/v5"


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ['res.partner', 'tmf.model.mixin']

    # TMF632 Party (Individual fields)
    tmf_given_name = fields.Char(string="givenName")
    tmf_family_name = fields.Char(string="familyName")

    # Common TMF status (examples in user guide include initialized/validated)
    tmf_managed = fields.Boolean(string="TMF Managed Party", default=False, index=True)

    tmf_status = fields.Selection([
        ('initialized', 'Initialized'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string="TMF Status", default='initialized')

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
