from odoo import models, fields

class TMFParty(models.Model):
    _name = 'tmf.party'
    _description = 'Party (generic placeholder model)'
    _inherit = ['tmf.model.mixin']

    # This model is optional; kept minimal to avoid install errors.
    name = fields.Char()
    tmf_status = fields.Selection([
        ("initialized", "initialized"),
        ("validated", "validated"),
        ("closed", "closed"),
    ], default="initialized", required=True)

    def _get_tmf_api_path(self):
        # Party API base path (TMF632)
        return "/tmf-api/partyManagement/v5"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id or str(self.id),
            "href": f"/tmf-api/partyManagement/v5/party/{self.tmf_id or self.id}",
            "@type": "Party",
            "name": self.name or "",
        }
