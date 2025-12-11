from odoo import models, fields


class TMFHubSubscription(models.Model):
    _name = 'tmf.hub.subscription'
    _description = 'TMF Event Hub Subscription'

    api_name = fields.Char(required=True)   # e.g. 'party', 'productOrder', 'service'
    callback = fields.Char(required=True)   # callback URL
    query = fields.Char()                   # optional filter expression
