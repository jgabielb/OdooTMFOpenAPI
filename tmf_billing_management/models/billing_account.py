from odoo import models, fields, api

class BillingAccount(models.Model):
    _name = 'tmf.billing.account'
    _description = 'TMF666 Billing Account'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Account Name", required=True)
    partner_id = fields.Many2one('res.partner', string="Account Holder", required=True)
    account_balance = fields.Monetary(string="Current Balance", compute="_compute_balance")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    state = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed')
    ], default='active', string="Status")

    def _compute_balance(self):
        for rec in self:
            try:
                rec.account_balance = rec.partner_id.total_due or 0.0
            except Exception:
                rec.account_balance = 0.0

    def _get_tmf_api_path(self):
        return "/accountManagement/v4/billingAccount"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "state": self.state,
            "@type": "BillingAccount",
            "accountBalance": [{
                "amount": {"value": self.account_balance, "unit": self.currency_id.name},
                "validFor": {"startDateTime": fields.Datetime.now().isoformat()}
            }],
            "relatedParty": [{
                "id": self.partner_id.tmf_id,
                "name": self.partner_id.name,
                "role": "AccountHolder"
            }]
        }

    # ==========================================
    # NOTIFICATION LOGIC
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('account', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        event_action = 'state_change' if 'state' in vals else 'update'
        for rec in self:
            self._notify('account', event_action, rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='account',
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