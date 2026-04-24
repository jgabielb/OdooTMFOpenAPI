# tmf_base/models/tmf_api_key.py
import uuid
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TmfApiKey(models.Model):
    _name = "tmf.api.key"
    _description = "TMF API Key"
    _order = "create_date desc"

    name = fields.Char(string="Name", required=True)
    key = fields.Char(
        string="API Key",
        required=True,
        copy=False,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        ondelete="set null",
    )
    is_active = fields.Boolean(string="Active", default=True)
    create_date = fields.Datetime(string="Created On", readonly=True)

    _key_unique = models.Constraint(
        "UNIQUE(key)",
        "API key must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("key"):
                vals["key"] = str(uuid.uuid4())
        return super().create(vals_list)
