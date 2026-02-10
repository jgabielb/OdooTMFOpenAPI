# -*- coding: utf-8 -*-
from odoo import models, fields


class TMF654BalanceAction(models.Model):
    """
    TMF654 BalanceAction (history entry for actions executed over a Bucket).
    In TMF654, BalanceAction is used to retrieve a history of tasks that act on a Bucket
    (TopupBalance, AdjustBalance, TransferBalance, ReserveBalance) and @type identifies
    the task type. :contentReference[oaicite:0]{index=0}
    """
    _name = "tmf654.balance.action"
    _description = "TMF654 BalanceAction"
    _rec_name = "tmf_id"
    _order = "requested_date desc, id desc"

    # TMF common
    tmf_id = fields.Char(string="id", required=True, index=True)
    href = fields.Char()
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    # In TMF654, @type indicates which task generated the history entry:
    # TopupBalance / AdjustBalance / TransferBalance / ReserveBalance. :contentReference[oaicite:1]{index=1}
    type = fields.Char(string="@type", required=True)

    # Generic action/task fields (align with task resources)
    description = fields.Char()
    reason = fields.Char()
    status = fields.Char()
    usage_type = fields.Char(string="usageType")

    requested_date = fields.Datetime(string="requestedDate")
    confirmation_date = fields.Datetime(string="confirmationDate")

    # Amount impacted (common summary fields)
    amount_value = fields.Float(string="amount.value")
    amount_units = fields.Char(string="amount.units")

    # Optional cost fields for transfers
    transfer_cost_value = fields.Float(string="transferCost.value")
    transfer_cost_units = fields.Char(string="transferCost.units")
    cost_owner = fields.Char(string="costOwner")

    # References (store as JSON text for flexibility, same pattern as your other modules)
    bucket_json = fields.Text(string="bucket")
    impacted_bucket_json = fields.Text(string="impactedBucket")
    channel_json = fields.Text(string="channel")
    party_account_json = fields.Text(string="partyAccount")
    product_json = fields.Text(string="product")
    logical_resource_json = fields.Text(string="logicalResource")
    related_party_json = fields.Text(string="relatedParty")
    requestor_json = fields.Text(string="requestor")

    # Receiver side refs (only relevant when @type == TransferBalance)
    receiver_json = fields.Text(string="receiver")
    receiver_bucket_json = fields.Text(string="receiverBucket")
    receiver_party_account_json = fields.Text(string="receiverPartyAccount")
    receiver_product_json = fields.Text(string="receiverProduct")
    receiver_logical_resource_json = fields.Text(string="receiverLogicalResource")
    receiver_bucket_usage_type = fields.Char(string="receiverBucketUsageType")

    # Optional linkage to the originating task records (not part of TMF payload, useful internally)
    topup_balance_id = fields.Many2one("tmf654.topup.balance", ondelete="set null")
    adjust_balance_id = fields.Many2one("tmf654.adjust.balance", ondelete="set null")
    transfer_balance_id = fields.Many2one("tmf654.transfer.balance", ondelete="set null")
    reserve_balance_id = fields.Many2one("tmf654.reserve.balance", ondelete="set null")

    # ---- Convenience helpers (optional) ----
    def to_tmf_dict(self):
        """
        Minimal serializer helper (controller can use this to emit BalanceActionHistory entries).
        Keep it simple and JSON-ready (dict); controller can add fields filtering if needed.
        """
        self.ensure_one()
        # NOTE: we don't json.loads here to avoid raising if stored text isn't valid JSON.
        # Your controller can json.loads safely with try/except like in other modules.
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.type,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
            "description": self.description,
            "reason": self.reason,
            "status": self.status,
            "usageType": self.usage_type,
            "requestedDate": self.requested_date.isoformat() if self.requested_date else None,
            "confirmationDate": self.confirmation_date.isoformat() if self.confirmation_date else None,
            "amount": {"amount": self.amount_value, "units": self.amount_units} if self.amount_units else None,
            "transferCost": {"amount": self.transfer_cost_value, "units": self.transfer_cost_units} if self.transfer_cost_units else None,
            "costOwner": self.cost_owner,
            "bucket": self.bucket_json,
            "impactedBucket": self.impacted_bucket_json,
            "channel": self.channel_json,
            "partyAccount": self.party_account_json,
            "product": self.product_json,
            "logicalResource": self.logical_resource_json,
            "relatedParty": self.related_party_json,
            "requestor": self.requestor_json,
            "receiver": self.receiver_json,
            "receiverBucket": self.receiver_bucket_json,
            "receiverPartyAccount": self.receiver_party_account_json,
            "receiverProduct": self.receiver_product_json,
            "receiverLogicalResource": self.receiver_logical_resource_json,
            "receiverBucketUsageType": self.receiver_bucket_usage_type,
        }
