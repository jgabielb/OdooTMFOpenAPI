from odoo import models, fields, api
import json
import pytz

def _dt_to_rfc3339_z(dt):
    """Odoo guarda datetime naive en UTC. Convertimos a string RFC3339 con Z."""
    if not dt:
        return None
    if isinstance(dt, str):
        dt = fields.Datetime.from_string(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    else:
        dt = dt.astimezone(pytz.UTC)
    return dt.isoformat().replace("+00:00", "Z")

class TroubleTicket(models.Model):
    _name = 'tmf.trouble.ticket'
    _description = 'TMF Trouble Ticket'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Ticket ID", default="New", readonly=True, index=True)
    description = fields.Text(string="Description", required=True)
    external_id = fields.Char(string="External ID")
    
    # Changed to Char for flexibility with TMF tests
    ticket_type = fields.Char(string="Ticket Type", default="Complaint")
    severity = fields.Char(string="Severity", default="Medium")
    priority = fields.Char(string="Priority", default="Medium")
    
    # Changed to Char to accept ANY status sent by TMF (e.g. 'In Progress', 'inProgress')
    status = fields.Char(string="Status", default="Submitted", index=True)
    
    status_change_reason = fields.Char(string="Status Change Reason")
    status_change_date = fields.Datetime(string="Status Change Date")
    
    creation_date = fields.Datetime(default=fields.Datetime.now, string="Creation Date", readonly=True)
    last_update = fields.Datetime(string="Last Update", compute="_compute_last_update", store=True)
    requested_resolution_date = fields.Datetime(string="Requested Resolution Date")
    expected_resolution_date = fields.Datetime(string="Expected Resolution Date")
    resolution_date = fields.Datetime(string="Resolution Date")

    partner_id = fields.Many2one('res.partner', string="Customer")
    service_id = fields.Many2one('tmf.service', string="Affected Service")
    channel = fields.Char(string="Channel")
    note = fields.Text(string="Notes")
    attachment = fields.Binary(string="Attachment")

    @api.depends('write_date')
    def _compute_last_update(self):
        for rec in self:
            rec.last_update = rec.write_date

    def _get_tmf_api_path(self):
        return "/troubleTicketManagement/v5/troubleTicket"
    
    def _normalize_status_for_ctk(self, status):
        if not status:
            return "acknowledged"

        s = str(status).strip()

        # normalizaciones comunes (CTK suele ser case-sensitive)
        aliases = {
            "Submitted": "acknowledged",
            "submitted": "acknowledged",
            "In Progress": "inProgress",
            "in progress": "inProgress",
            "inProgress": "inProgress",
            "Pending": "pending",
            "pending": "pending",
            "Resolved": "resolved",
            "resolved": "resolved",
            "Closed": "closed",
            "closed": "closed",
            "Cancelled": "cancelled",
            "Canceled": "cancelled",
            "cancelled": "cancelled",
            "cancelled": "cancelled",
            "Rejected": "rejected",
            "rejected": "rejected",
        }

        s = aliases.get(s, s)

        allowed = {
            "acknowledged",
            "inProgress",
            "pending",
            "resolved",
            "closed",
            "rejected",
            "cancelled",
        }

        return s if s in allowed else "acknowledged"


    def to_tmf_json(self):
        self.ensure_one()
        href = getattr(self, 'tmf_href', f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}")

        data = {
            "id": str(self.tmf_id or self.id),
            "href": href,
            "@type": "TroubleTicket",
            "name": self.name,
            "description": self.description,
            "ticketType": self.ticket_type,
            "severity": self.severity,
            "priority": self.priority,
            "status": self._normalize_status_for_ctk(self.status),
            # "statusChangeReason": self.status_change_reason,
            "relatedParty": [],
            "relatedEntity": []
        }

        if self.status_change_reason:
            data["statusChangeReason"] = self.status_change_reason

        # Solo agregar fechas si existen (evita null)
        creation = _dt_to_rfc3339_z(self.creation_date)
        if creation:
            data["creationDate"] = creation

        last_update = _dt_to_rfc3339_z(self.last_update)
        if last_update:
            data["lastUpdate"] = last_update

        req = _dt_to_rfc3339_z(self.requested_resolution_date)
        if req:
            data["requestedResolutionDate"] = req

        exp = _dt_to_rfc3339_z(self.expected_resolution_date)
        if exp:
            data["expectedResolutionDate"] = exp

        res = _dt_to_rfc3339_z(self.resolution_date)
        if res:
            data["resolutionDate"] = res

        if self.partner_id:
            data["relatedParty"].append({
                "id": str(self.partner_id.tmf_id or self.partner_id.id),
                "name": self.partner_id.name,
                "role": "Customer",
                "@referredType": "Individual"
            })

        return data

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                 vals['name'] = 'TT-' + fields.Datetime.now().strftime('%Y%m%d%H%M%S')
        return super().create(vals_list)
    
    # ---------------- EVENT HOOKS FOR /hub (TMF621) ----------------

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',  # o 'troubleTicketManagement' si así lo manejas
                    event_type='TroubleTicketCreateEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                # nunca romper create si falla notificación
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',
                    event_type='TroubleTicketAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',
                    event_type='TroubleTicketDeleteEvent',
                    resource_json=payload,
                )
            except Exception:
                continue
        return res