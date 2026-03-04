from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.transfer.balance'
    _description = 'TransferBalance'
    _inherit = ['tmf.model.mixin']

    confirmation_date = fields.Datetime(string="confirmationDate", help="Date when the deduction was confirmed in the server")
    cost_owner = fields.Char(string="costOwner", help="Indicates which related party will bear the costs of the transfer. eg originator or receiver")
    description = fields.Char(string="description", help="Description of the recharge operation")
    reason = fields.Char(string="reason", help="Text describing the reason for the action/task")
    receiver_bucket_usage_type = fields.Char(string="receiverBucketUsageType", help="Type of prepay balance bucket (e.g.: roaming-data, data, roaming-voice etc)")
    requested_date = fields.Datetime(string="requestedDate", help="Date when the deduction request was received in the server")
    status = fields.Char(string="status", help="Status of the operation")
    usage_type = fields.Char(string="usageType", help="defines the type of the underlying Balance eg data,voice, any currency eg EUR, USD etc")
    amount = fields.Char(string="amount", help="Indicate the amount on the bucket. This is always a postive value. If part of an AdjustBalance then ")
    bucket = fields.Char(string="bucket", help="A reference to the bucket impacted by the request or the value itself.")
    channel = fields.Char(string="channel", help="Indicator for the channel used to request the transfer operation. Structure including at least attri")
    impacted_bucket = fields.Char(string="impactedBucket", help="A reference to the bucket impacted by the request or the value itself.")
    logical_resource = fields.Char(string="logicalResource", help="A reference to the logical resource that can be used to identify the bucket balance for example wher")
    party_account = fields.Char(string="partyAccount", help="A reference to the account that owns the bucket impacted by the balance related operation")
    product = fields.Char(string="product", help="A reference to the Product associated with this bucket")
    receiver = fields.Char(string="receiver", help="Identifier for the user/customer/entity that receives the transfer when it is required to indicate a")
    receiver_bucket = fields.Char(string="receiverBucket", help="A reference to the bucket to which the balance will be transferred")
    receiver_logical_resource = fields.Char(string="receiverLogicalResource", help="A reference to the logical resource that can be used to identify the bucket balance for example wher")
    receiver_party_account = fields.Char(string="receiverPartyAccount", help="A reference to the receiver account that owns the receiverlbucket impacted by the balance related op")
    receiver_product = fields.Char(string="receiverProduct", help="")
    related_party = fields.Char(string="relatedParty", help="Used to provide information about any other entity with relation to the operation")
    requestor = fields.Char(string="requestor", help="Identifier for the user/customer/entity that performs the top-up action. This can be used to indicat")
    transfer_cost = fields.Char(string="transferCost", help="Associated cost to be charged for the transfer operation (can be monetary or non-monetary)")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    account_payment_id = fields.Many2one("account.payment", string="Account Payment", ondelete="set null")
    account_move_id = fields.Many2one("account.move", string="Account Move", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/transfer_balanceManagement/v4/TransferBalance"

    def _safe_json(self, value, default):
        if not value:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    def _resolve_partner(self):
        self.ensure_one()
        refs = self._safe_json(self.related_party, [])
        if isinstance(refs, dict):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        env_partner = self.env["res.partner"].sudo()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (ref.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _sync_native_links(self):
        env_payment = self.env["account.payment"].sudo()
        env_move = self.env["account.move"].sudo()
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            if not rec.account_payment_id and rec.partner_id:
                pay = env_payment.search([("partner_id", "=", rec.partner_id.id)], limit=1, order="id desc")
                if pay:
                    rec.account_payment_id = pay.id
            if not rec.account_move_id and rec.partner_id:
                move = env_move.search([("partner_id", "=", rec.partner_id.id), ("move_type", "in", ["out_invoice", "out_refund"])], limit=1, order="id desc")
                if move:
                    rec.account_move_id = move.id

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "TransferBalance",
            "confirmationDate": self.confirmation_date.isoformat() if self.confirmation_date else None,
            "costOwner": self.cost_owner,
            "description": self.description,
            "reason": self.reason,
            "receiverBucketUsageType": self.receiver_bucket_usage_type,
            "requestedDate": self.requested_date.isoformat() if self.requested_date else None,
            "status": self.status,
            "usageType": self.usage_type,
            "amount": self.amount,
            "bucket": self.bucket,
            "channel": self.channel,
            "impactedBucket": self.impacted_bucket,
            "logicalResource": self.logical_resource,
            "partyAccount": self.party_account,
            "product": self.product,
            "receiver": self.receiver,
            "receiverBucket": self.receiver_bucket,
            "receiverLogicalResource": self.receiver_logical_resource,
            "receiverPartyAccount": self.receiver_party_account,
            "receiverProduct": self.receiver_product,
            "relatedParty": self.related_party,
            "requestor": self.requestor,
            "transferCost": self.transfer_cost,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_native_links()
        for rec in recs:
            self._notify('transferBalance', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "related_party" in vals or "partner_id" in vals or "account_payment_id" in vals or "account_move_id" in vals:
            self._sync_native_links()
        for rec in self:
            self._notify('transferBalance', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='transferBalance',
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
