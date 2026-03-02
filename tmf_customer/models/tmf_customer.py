import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class TMFCustomer(models.Model):
    _name = 'tmf.customer'
    _description = 'TMF Customer'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Name", required=True)
    
    # Link to Odoo's native Contact
    partner_id = fields.Many2one(
        "res.partner",
        string="Related Party",
        required=True,
        ondelete="cascade",
        help="Underlying Odoo partner representing this customer."
    )

    # External references
    external_id = fields.Char(string="External ID", help="ID from legacy/external systems")
    
    description = fields.Text(string="Description")

    # Lifecycle Management (Must be Selection to match DB)
    status = fields.Selection([
        ('initialized', 'Initialized'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string="Status", default='active', required=True)
    
    lifecycle_status = fields.Selection([
        ('prospect', 'Prospect'),
        ('active', 'Active'),
        ('terminated', 'Terminated')
    ], string="Lifecycle Status", default='active', required=True)

    def _get_tmf_api_path(self):
        return "/customerManagement/v5/customer"

    # ==========================================
    # SERIALIZATION (Odoo -> TMF JSON)
    # ==========================================
    def to_tmf_json(self):
        """Map this record to a TMF629 JSON representation."""
        self.ensure_one()
        
        # Base Data
        result = {
            "id": self.tmf_id or str(self.id),
            "href": self.href,
            "name": self.name,
            "status": self.status,
            "lifecycleStatus": self.lifecycle_status,
            "description": self.description or "",
            "externalId": self.external_id or "",
            "@type": "Customer"
        }

        # Link to Party (Standard TMF Pattern)
        if self.partner_id:
            result["party"] = {
                "id": self.partner_id.tmf_id or str(self.partner_id.id),
                "name": self.partner_id.name,
                "@type": "RelatedParty",
                "@referredType": "Organization" if self.partner_id.is_company else "Individual"
            }
            # Also add EngagedParty if needed by specific consumers
            result["engagedParty"] = {
                "id": self.partner_id.tmf_id or str(self.partner_id.id),
                "name": self.partner_id.name,
                "@type": "RelatedParty",
                "@referredType": "Organization" if self.partner_id.is_company else "Individual"
            }

        return result

    # ==========================================
    # DESERIALIZATION (TMF JSON -> Odoo)
    # ==========================================
    @api.model
    def map_tmf_to_odoo(self, data):
        """
        Helper to parse incoming JSON for Create/Update.
        """
        vals = {}
        
        # Direct Mapping
        if 'name' in data: vals['name'] = data['name']
        if 'status' in data: vals['status'] = data['status']
        if 'lifecycleStatus' in data: vals['lifecycle_status'] = data['lifecycleStatus']
        if 'description' in data: vals['description'] = data['description']
        if 'externalId' in data: vals['external_id'] = data['externalId']

        # Party Logic: If generic "party" or "engagedParty" is provided
        party_data = data.get("party") or data.get("engagedParty")
        
        if party_data:
            partner = self.env['res.partner']
            party_id = party_data.get("id")
            party_name = party_data.get("name")

            if party_id:
                # 1. Try to find existing partner by TMF id
                partner = self.env['res.partner'].sudo().search([('tmf_id', '=', str(party_id))], limit=1)
                # 2. Fallback to native numeric partner id
                if not partner and str(party_id).isdigit():
                    partner = self.env['res.partner'].sudo().browse(int(party_id))
                    if not partner.exists():
                        partner = self.env['res.partner']

            # 3. Fallback by name when id is absent/unresolved
            if not partner and party_name:
                partner = self.env['res.partner'].sudo().search([('name', '=', party_name)], limit=1)

            # 4. Create partner as last resort when engagedParty is present
            if not partner:
                create_vals = {'name': party_name or vals.get('name') or data.get('name') or 'TMF Customer'}
                if party_id:
                    create_vals['tmf_id'] = str(party_id)
                partner = self.env['res.partner'].sudo().create(create_vals)

            if partner and partner.exists():
                # Keep a stable external link when payload includes an external party id
                if party_id and not partner.tmf_id:
                    partner.sudo().write({'tmf_id': str(party_id)})
                vals['partner_id'] = partner.id
        
        # Fallback: If creating and no partner found, create one
        if 'partner_id' not in vals and data.get('name'):
            # Only do this if we are in a Create context (logic handled by controller)
            pass 

        return vals

    # ==========================================
    # NOTIFICATION LOGIC (Central Hub)
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('customer', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            # Smart detection of update vs state change
            event = 'state_change' if 'status' in vals or 'lifecycle_status' in vals else 'update'
            self._notify('customer', event, rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='customer',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        """Delegates notification to the TMF Base Hub"""
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception as e:
            _logger.error(f"Failed to send TMF notification: {e}")
