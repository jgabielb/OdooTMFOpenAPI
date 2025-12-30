from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.service.order'
    _description = 'ServiceOrder'
    _inherit = ['tmf.model.mixin']

    cancellation_date = fields.Datetime(string="cancellationDate", help="Date when the order is cancelled. This is used when order is cancelled. ")
    cancellation_reason = fields.Char(string="cancellationReason", help="Reason why the order is cancelled. This is used when order is cancelled. ")
    category = fields.Char(string="category", help="Used to categorize the order, useful for the OM system, such as: Broadband, TVOption")
    completion_date = fields.Datetime(string="completionDate", help="Effective delivery date amended by the provider")
    description = fields.Char(string="description", help="A free-text description of the service order")
    expected_completion_date = fields.Datetime(string="expectedCompletionDate", help="Expected delivery date amended by the provider")
    external_id = fields.Char(string="externalId", help="ID given by the consumer to facilitate searches")
    notification_contact = fields.Char(string="notificationContact", help="Contact attached to the order to send back information regarding this order")
    order_date = fields.Datetime(string="orderDate", help="")
    priority = fields.Char(string="priority", help="Can be used by consumers to prioritize orders in a Service Order Management system")
    requested_completion_date = fields.Datetime(string="requestedCompletionDate", help="Requested delivery date from the requestors perspective")
    requested_start_date = fields.Datetime(string="requestedStartDate", help="Order start date wished by the requestor")
    start_date = fields.Datetime(string="startDate", help="Date when the order was started for processing")
    error_message = fields.Char(string="errorMessage", help="the error message if the order closed by an error")
    external_reference = fields.Char(string="externalReference", help="")
    jeopardy_alert = fields.Char(string="jeopardyAlert", help="A list of jeopardy alerts related to this order")
    milestone = fields.Char(string="milestone", help="A list of milestones related to this order")
    note = fields.Char(string="note", help="Extra-information about the order; e.g. useful to add extra delivery information that could be usefu")
    order_relationship = fields.Char(string="orderRelationship", help="A list of service orders related to this order (e.g. prerequisite, dependent on)")
    related_party = fields.Char(string="relatedParty", help="A list of parties which are involved in this order and the role they are playing")
    service_order_item = fields.Char(string="serviceOrderItem", help="A list of service order items to be processed by this order")
    state = fields.Char(string="state", help="State of the order: described in the state-machine diagram")

    def _get_tmf_api_path(self):
        return "/service_orderManagement/v4/ServiceOrder"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ServiceOrder",
            "cancellationDate": self.cancellation_date.isoformat() if self.cancellation_date else None,
            "cancellationReason": self.cancellation_reason,
            "category": self.category,
            "completionDate": self.completion_date.isoformat() if self.completion_date else None,
            "description": self.description,
            "expectedCompletionDate": self.expected_completion_date.isoformat() if self.expected_completion_date else None,
            "externalId": self.external_id,
            "notificationContact": self.notification_contact,
            "orderDate": self.order_date.isoformat() if self.order_date else None,
            "priority": self.priority,
            "requestedCompletionDate": self.requested_completion_date.isoformat() if self.requested_completion_date else None,
            "requestedStartDate": self.requested_start_date.isoformat() if self.requested_start_date else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "errorMessage": self.error_message,
            "externalReference": self.external_reference,
            "jeopardyAlert": self.jeopardy_alert,
            "milestone": self.milestone,
            "note": self.note,
            "orderRelationship": self.order_relationship,
            "relatedParty": self.related_party,
            "serviceOrderItem": self.service_order_item,
            "state": self.state,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('serviceOrder', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('serviceOrder', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceOrder',
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
