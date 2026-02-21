# tmf_base/models/tmf_mixin.py
import uuid
from odoo import models, fields, api

class TMFModelMixin(models.AbstractModel):
    """
    Abstract Class to provide TMF compliance to any Odoo model.
    Implements:
    - Universal ID (UUID)
    - HREF generation
    - Common TMF timestamps
    """
    _name = 'tmf.model.mixin'
    _description = 'TM Forum Common Attributes'

    # 1. TMF ID (String/UUID) - The bridge to external systems
    tmf_id = fields.Char(
        string="TMF ID",
        default=lambda self: str(uuid.uuid4()),
        required=True,
        index=True,
        readonly=True,
        copy=False,
        help="Unique identifier used in TMF API calls."
    )

    # 2. HREF - Self-referencing URL required by TMF
    href = fields.Char(
        string="HREF",
        compute="_compute_href",
        help="API Reference URL"
    )

    # 3. Polymorphism (Optional but recommended)
    # TMF uses @type to distinguish objects (e.g., Individual vs Organization)
    tmf_type = fields.Char(string="@type", compute="_compute_tmf_type")

    @api.depends('tmf_id')
    def _compute_href(self):
        """
        Generates the API URL.
        Logic: base_url + api_path + tmf_id
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            api_path = record._get_tmf_api_path()
            if api_path and record.tmf_id:
                normalized_path = api_path if str(api_path).startswith("/tmf-api") else f"/tmf-api{api_path}"
                record.href = f"{base_url}{normalized_path}/{record.tmf_id}"
            else:
                record.href = False

    def _compute_tmf_type(self):
        """
        Default implementation. Can be overridden by child models.
        """
        for record in self:
            record.tmf_type = record._name

    @api.model
    def _get_tmf_api_path(self):
        """
        Placeholder. Child models MUST override this.
        Example return: '/party/v4/individual'
        """
        return ""
    
    @property
    def tmf_href(self):
        """Default href builder using api path + tmf_id/id."""
        self.ensure_one()
        path = self._get_tmf_api_path() or ""
        if not path:
            return None
        base = path if str(path).startswith("/tmf-api") else "/tmf-api" + path
        return f"{base}/{self.tmf_id or self.id}"
    
    def _register_hook(self):
        # Register the unique constraint on the SQL table
        # We use a raw SQL constraint for mixins or define it on the child model
        pass
    
    # _sql_constraints = [
    #     ('tmf_id_uniq', 'unique (tmf_id)', 'The TMF ID must be unique!')
    # ]
