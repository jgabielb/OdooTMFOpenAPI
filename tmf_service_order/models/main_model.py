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
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    project_task_id = fields.Many2one("project.task", string="Fulfillment Task", ondelete="set null")

    # --- JSON fields (CTK REQUIRED) ---
    service_order_item = fields.Json(string="serviceOrderItem")
    related_party = fields.Json(string="relatedParty")
    note = fields.Json(string="note")
    external_reference = fields.Json(string="externalReference")
    milestone = fields.Json(string="milestone")
    jeopardy_alert = fields.Json(string="jeopardyAlert")
    order_relationship = fields.Json(string="orderRelationship")
    error_message = fields.Json(string="errorMessage")

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        parties = self.related_party or []
        if not isinstance(parties, list):
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo()
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            if not pid:
                continue
            partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
            if not partner and str(pid).isdigit():
                partner = Partner.browse(int(pid))
            if partner and partner.exists():
                return partner
        return self.env["res.partner"]

    def _sync_project_task(self):
        """
        Wire TMF641 service orders into Odoo Project as fulfillment tasks.
        """
        Task = self.env["project.task"].sudo()
        Project = self.env["project.project"].sudo()
        for rec in self:
            partner = rec.partner_id
            if not partner:
                partner = rec._resolve_partner_from_related_party()
                if partner and partner.exists():
                    rec.partner_id = partner.id

            project = Project.search([], limit=1)
            vals = {
                "name": rec.description or f"TMF ServiceOrder {rec.tmf_id or rec.id}",
                "description": rec.description or "",
                "partner_id": partner.id if partner and partner.exists() else False,
                "date_deadline": rec.requested_completion_date.date() if rec.requested_completion_date else False,
            }
            if project:
                vals["project_id"] = project.id

            if rec.project_task_id and rec.project_task_id.exists():
                rec.project_task_id.write(vals)
            else:
                rec.project_task_id = Task.create(vals).id

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ServiceOrderCreateEvent",
            "update": "ServiceOrderAttributeValueChangeEvent",
            "delete": "ServiceOrderDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("serviceOrder", event_name, payload)
            except Exception:
                continue

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

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_project_task()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._sync_project_task()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
