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

    # Mapping Odoo Fields to TMF JSON Structure
    # We don't need to create new columns for Name/Email because Odoo has them,
    # but we will need logic later to map them in the API.

    def _get_tmf_api_path(self):
        """
        Override from Mixin. 
        Determines the URL based on if it's a Company or Individual.
        """
        self.ensure_one()
        if self.is_company:
            return "/party/v4/organization"
        return "/party/v4/individual"