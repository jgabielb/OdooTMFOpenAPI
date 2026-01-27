from odoo import fields, models

class TMF640Hub(models.Model):
    _name = "tmf640.hub"
    _description = "TMF640 Hub Listener"

    callback = fields.Char(required=True)
    query = fields.Char()
