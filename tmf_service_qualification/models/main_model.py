from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class ServiceQualification(models.Model):
    _name = 'tmf.service.qualification'
    _description = 'Service Qualification (Feasibility Check)'
    _inherit = ['tmf.model.mixin']

    # 1. Inputs
    description = fields.Text(string="Description")
    
    # Link to the Address being checked
    place_id = fields.Many2one(
        'tmf.geographic.address', 
        string="Service Address",
        required=True
    )
    
    # Link to the Technical Spec (e.g., Fiber Internet)
    service_specification_id = fields.Many2one(
        'tmf.product.specification', 
        string="Service Specification",
        required=True
    )

    # 2. Outputs - THESE MUST BE SELECTION FIELDS
    state = fields.Selection([
        ('inProgress', 'In Progress'),
        ('done', 'Done'),
        ('terminatedWithError', 'Error')
    ], default='inProgress', string="State")

    qualification_result = fields.Selection([
        ('qualified', 'Qualified'),
        ('unqualified', 'Unqualified')
    ], string="Result", readonly=True)

    expiration_date = fields.Datetime(string="Expiration Date")

    def _get_tmf_api_path(self):
        return "/serviceQualificationManagement/v4/checkServiceQualification"

    # ==========================================
    # THE BRAIN: Feasibility Logic
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._run_feasibility_check()
        return recs

    def _run_feasibility_check(self):
        self.ensure_one()
        target_city = self.place_id.city or ""
        
        # Logic: Only 'Santiago' works
        if "Santiago" in target_city:
            self.qualification_result = 'qualified'
            self.description = "Fiber is available in this area."
        else:
            self.qualification_result = 'unqualified'
            self.description = f"No coverage available in {target_city}."

        self.state = 'done'
        self.expiration_date = fields.Datetime.add(fields.Datetime.now(), days=7)

    # ==========================================
    # SERIALIZATION
    # ==========================================
    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "state": self.state,
            "qualificationResult": self.qualification_result,
            "effectiveQualificationDate": fields.Datetime.now().isoformat(),
            "expirationDate": self.expiration_date.isoformat() if self.expiration_date else None,
            "serviceSpecification": {
                "id": self.service_specification_id.tmf_id,
                "name": self.service_specification_id.name
            },
            "place": {
                "id": self.place_id.tmf_id,
                "role": "installationAddress",
                "@type": "GeographicAddress"
            }
        }