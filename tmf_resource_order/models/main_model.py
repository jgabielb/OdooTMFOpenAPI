from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.resource.order'
    _description = 'ResourceOrder'
    _inherit = ['tmf.model.mixin']

    cancellation_date = fields.Datetime(string="cancellationDate", help="Date when the order is cancelled - if cancelled, in RFC3339 (subset of ISO8601) format")
    cancellation_reason = fields.Char(string="cancellationReason", help="Reason why the order is cancelled - if cancelled")
    category = fields.Char(string="category", help="Used to categorize the order from a business perspective that can be useful for the order management")
    completion_date = fields.Datetime(string="completionDate", help="Date when the order was actually completed, in RFC3339 (subset of ISO8601) format")
    description = fields.Char(string="description", help="Free-text description of the Resource Order")
    expected_completion_date = fields.Datetime(string="expectedCompletionDate", help="Date when the order is expected to be completed, in RFC3339 (subset of ISO8601) format")
    external_id = fields.Char(string="externalId", help="DEPRECATED: Use externalReference Instead. ID given by the consumer (to facilitate searches afterwar")
    name = fields.Char(string="name", help="A string used to give a name to the Resource Order")
    order_date = fields.Datetime(string="orderDate", help="Date when the order was created, in RFC3339 (subset of ISO8601) format")
    order_type = fields.Char(string="orderType", help="Name of the Resource Order type")
    priority = fields.Integer(string="priority", help="A way that can be used by consumers to prioritize orders in OM system (such as: 0 is the highest pri")
    requested_completion_date = fields.Datetime(string="requestedCompletionDate", help="Requested delivery date from the requestor perspective, in RFC3339 (subset of ISO8601) format")
    requested_start_date = fields.Datetime(string="requestedStartDate", help="Order start date wished by the requestor, in RFC3339 (subset of ISO8601) format")
    start_date = fields.Datetime(string="startDate", help="Date when the order was actually started, in RFC3339 (subset of ISO8601) format")
    external_reference = fields.Char(string="externalReference", help="")
    note = fields.Char(string="note", help="")
    order_item = fields.Char(string="orderItem", help="")
    related_party = fields.Char(string="relatedParty", help="")
    state = fields.Char(string="state", help="")

    def _get_tmf_api_path(self):
        return "/resource_orderManagement/v4/ResourceOrder"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ResourceOrder",
            "cancellationDate": self.cancellation_date.isoformat() if self.cancellation_date else None,
            "cancellationReason": self.cancellation_reason,
            "category": self.category,
            "completionDate": self.completion_date.isoformat() if self.completion_date else None,
            "description": self.description,
            "expectedCompletionDate": self.expected_completion_date.isoformat() if self.expected_completion_date else None,
            "externalId": self.external_id,
            "name": self.name,
            "orderDate": self.order_date.isoformat() if self.order_date else None,
            "orderType": self.order_type,
            "priority": self.priority,
            "requestedCompletionDate": self.requested_completion_date.isoformat() if self.requested_completion_date else None,
            "requestedStartDate": self.requested_start_date.isoformat() if self.requested_start_date else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "externalReference": self.external_reference,
            "note": self.note,
            "orderItem": self.order_item,
            "relatedParty": self.related_party,
            "state": self.state,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('resourceOrder', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('resourceOrder', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='resourceOrder',
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
