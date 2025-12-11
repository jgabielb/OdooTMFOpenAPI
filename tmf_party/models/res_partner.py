from odoo import models, fields, api

class ResPartner(models.Model):
    # We inherit 'res.partner' to add fields to it
    # We inherit 'tmf.model.mixin' to get the UUID and HREF logic
    _name = 'res.partner'
    _inherit = ['res.partner', 'tmf.model.mixin']

    # TMF Specific Fields
    # status: TMF lifecycle (initialized, validated, active)
    tmf_status = fields.Selection([
        ('initialized', 'Initialized'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string="TMF Status", default='active')

    # Simple TMF-ish classification
    tmf_customer_type = fields.Selection([
        ('individual', 'Individual'),
        ('organization', 'Organization'),
    ], string="TMF Party Type")

    # Mapping Odoo Fields to TMF JSON Structure
    # We don't need to create new columns for Name/Email because Odoo has them,
    # but we will need logic later to map them in the API.

    def _compute_tmf_type(self):
        """Helper to decide TMF type."""
        self.ensure_one()
        if self.tmf_customer_type:
            return self.tmf_customer_type
        return 'organization' if self.is_company else 'individual'
    
    def to_tmf_json(self):
        """Return TMF632 Individual/Organization representation."""
        self.ensure_one()

        party_type = self._compute_tmf_type()
        is_individual = party_type == 'individual'

        # Decide base path
        if is_individual:
            base_path = "/party/v4/individual"
            tmf_type = "Individual"
        else:
            base_path = "/party/v4/organization"
            tmf_type = "Organization"

        tmf_id = self.tmf_id or str(self.id)
        href = f"/tmf-api{base_path}/{tmf_id}"

        data = {
            "id": tmf_id,
            "href": href,
            "@type": tmf_type,
        }

        if is_individual:
            # Very simplified Individual
            data.update({
                "givenName": self.name,  # or split name components if you want
                "contactMedium": [{
                    "mediumType": "email",
                    "preferred": True,
                    "characteristic": {"emailAddress": self.email},
                }] if self.email else [],
            })
        else:
            # Very simplified Organization
            data.update({
                "name": self.name,
                "contactMedium": [{
                    "mediumType": "email",
                    "preferred": True,
                    "characteristic": {"emailAddress": self.email},
                }] if self.email else [],
            })

        # Optionally add telecom, address, etc. here

        return data

    # ---------- Event hooks for Party /hub ----------

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='party',
                event_type='PartyCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='party',
                    event_type='PartyAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [p.to_tmf_json() for p in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='party',
                    event_type='PartyDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
    
    def _get_tmf_api_path(self):
        """
        Override from Mixin. 
        Determines the URL based on if it's a Company or Individual.
        """
        self.ensure_one()
        if self.is_company:
            return "/party/v4/organization"
        return "/party/v4/individual"