from odoo import models, fields, api
import json
from datetime import datetime

class TMFServiceOrder(models.Model):
    _name = 'tmf.service.order'
    _description = 'ServiceOrder'
    _inherit = ['tmf.model.mixin']

    # --- Scalar fields ---
    external_id = fields.Char(string="externalId")
    description = fields.Char(string="description")
    category = fields.Char(string="category")
    priority = fields.Char(string="priority")
    notification_contact = fields.Char(string="notificationContact")

    requested_start_date = fields.Datetime(string="requestedStartDate")
    requested_completion_date = fields.Datetime(string="requestedCompletionDate")
    expected_completion_date = fields.Datetime(string="expectedCompletionDate")

    order_date = fields.Datetime(string="orderDate")
    start_date = fields.Datetime(string="startDate")
    completion_date = fields.Datetime(string="completionDate")

    cancellation_date = fields.Datetime(string="cancellationDate")
    cancellation_reason = fields.Char(string="cancellationReason")

    state = fields.Char(string="state")

    # --- JSON fields (CTK REQUIRED) ---
    service_order_item = fields.Json(string="serviceOrderItem")
    related_party = fields.Json(string="relatedParty")
    note = fields.Json(string="note")
    external_reference = fields.Json(string="externalReference")
    milestone = fields.Json(string="milestone")
    jeopardy_alert = fields.Json(string="jeopardyAlert")
    order_relationship = fields.Json(string="orderRelationship")
    error_message = fields.Json(string="errorMessage")

    def _get_tmf_api_path(self):
        return "/serviceOrdering/v4/serviceOrder"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ServiceOrder",
            "externalId": self.external_id,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "state": self.state,
            "notificationContact": self.notification_contact,
            "orderDate": self.order_date.isoformat() if self.order_date else None,
            "requestedStartDate": self.requested_start_date.isoformat() if self.requested_start_date else None,
            "requestedCompletionDate": self.requested_completion_date.isoformat() if self.requested_completion_date else None,
            "expectedCompletionDate": self.expected_completion_date.isoformat() if self.expected_completion_date else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "completionDate": self.completion_date.isoformat() if self.completion_date else None,
            "cancellationDate": self.cancellation_date.isoformat() if self.cancellation_date else None,
            "cancellationReason": self.cancellation_reason,
            "serviceOrderItem": self.service_order_item,
            "relatedParty": self.related_party,
            "note": self.note,
            "externalReference": self.external_reference,
            "milestone": self.milestone,
            "jeopardyAlert": self.jeopardy_alert,
            "orderRelationship": self.order_relationship,
            "errorMessage": self.error_message,
        }
