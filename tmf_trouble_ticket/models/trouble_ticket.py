from odoo import models, fields, api
import json

class TroubleTicket(models.Model):
    _name = 'tmf.trouble.ticket'
    _description = 'TMF Trouble Ticket'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Ticket ID", default="New", readonly=True)
    description = fields.Text(string="Description", required=True)
    severity = fields.Selection([
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical')
    ], default='Medium', string="Severity")
    
    type = fields.Char(string="Ticket Type", default="Complaint")
    
    creation_date = fields.Datetime(default=fields.Datetime.now, string="Creation Date")
    resolution_date = fields.Datetime(string="Resolution Date")

    status = fields.Selection([
        ('Submitted', 'Submitted'),
        ('InProgress', 'In Progress'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
        ('Rejected', 'Rejected')
    ], default='Submitted', string="Status")

    # Relationships
    partner_id = fields.Many2one('res.partner', string="Customer")
    service_id = fields.Many2one('tmf.service', string="Affected Service")

    def _get_tmf_api_path(self):
        return "/troubleTicketManagement/v4/troubleTicket"

    @property
    def tmf_href(self):
        base = "/tmf-api" + self._get_tmf_api_path()
        return f"{base}/{self.tmf_id}"

    # =======================================================
    # 1. Serialization (Odoo Object -> TMF JSON)
    # =======================================================
    def to_tmf_json(self):
        self.ensure_one()
        ticket_id = self.tmf_id or str(self.id)
        
        data = {
            "id": ticket_id,
            "href": self.tmf_href,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "type": self.type,
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "resolutionDate": self.resolution_date.isoformat() if self.resolution_date else None,
            "status": self.status,
            "@type": "TroubleTicket",
            "relatedParty": [],
            "relatedEntity": []
        }

        # Link Customer
        if self.partner_id:
            data["relatedParty"].append({
                "id": self.partner_id.tmf_id,
                "name": self.partner_id.name,
                "role": "Customer",
                "@reference": self.partner_id.name
            })

        # Link Service
        if self.service_id:
            data["relatedEntity"].append({
                "id": self.service_id.tmf_id,
                "name": self.service_id.name,
                "@type": "Service",
                "@referredType": "Service"
            })

        return data

    # =======================================================
    # 2. CRUD Overrides (The Notification Triggers)
    # =======================================================
    @api.model_create_multi
    def create(self, vals_list):
        # 1. Handle Auto-Sequence for every record in the list
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('tmf.trouble.ticket') or 'TT-0000'
        
        # 2. Call super to create the records in the database
        recs = super(TroubleTicket, self).create(vals_list)
        
        # 3. Trigger Notifications for EACH new record
        for rec in recs:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',
                    event_type='TroubleTicketCreateEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                pass 
                
        return recs

    def write(self, vals):
        res = super(TroubleTicket, self).write(vals)
        
        # Determine Event Type
        event_type = 'TroubleTicketAttributeValueChangeEvent'
        if 'status' in vals:
            event_type = 'TroubleTicketStatusChangeEvent'

        for rec in self:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',
                    event_type=event_type,
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super(TroubleTicket, self).unlink()
        
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='troubleTicket',
                    event_type='TroubleTicketDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res