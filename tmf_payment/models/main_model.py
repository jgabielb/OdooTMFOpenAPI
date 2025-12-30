from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.payment'
    _description = 'Payment'
    _inherit = ['tmf.model.mixin']

    authorization_code = fields.Char(string="authorizationCode", help="Authorization code retrieved from an external payment gateway that could be used for conciliation")
    correlator_id = fields.Char(string="correlatorId", help="Unique identifier in the client for the payment in case it is needed to correlate")
    description = fields.Char(string="description", help="Text describing the contents of the payment")
    name = fields.Char(string="name", help="Screen name of the payment")
    payment_date = fields.Datetime(string="paymentDate", help="Date when the payment was performed")
    status = fields.Char(string="status", help="Status of the payment")
    status_date = fields.Datetime(string="statusDate", help="Date when the status was recorded")
    account = fields.Char(string="account", help="")
    amount = fields.Char(string="amount", help="Amount to be paid (net of taxes)")
    channel = fields.Char(string="channel", help="")
    payment_item = fields.Char(string="paymentItem", help="")
    payment_method = fields.Char(string="paymentMethod", help="")
    point_of_interaction = fields.Char(string="pointOfInteraction", help="")
    related_party = fields.Char(string="relatedParty", help="")
    tax_amount = fields.Char(string="taxAmount", help="Tax applied")
    total_amount = fields.Char(string="totalAmount", help="Amount to be paid (including taxes)")

    def _get_tmf_api_path(self):
        return "/paymentManagement/v4/Payment"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Payment",
            "authorizationCode": self.authorization_code,
            "correlatorId": self.correlator_id,
            "description": self.description,
            "name": self.name,
            "paymentDate": self.payment_date.isoformat() if self.payment_date else None,
            "status": self.status,
            "statusDate": self.status_date.isoformat() if self.status_date else None,
            "account": self.account,
            "amount": self.amount,
            "channel": self.channel,
            "paymentItem": self.payment_item,
            "paymentMethod": self.payment_method,
            "pointOfInteraction": self.point_of_interaction,
            "relatedParty": self.related_party,
            "taxAmount": self.tax_amount,
            "totalAmount": self.total_amount,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('payment', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('payment', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='payment',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
