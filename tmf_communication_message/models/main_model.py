from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.communication.message'
    _description = 'CommunicationMessage'
    _inherit = ['tmf.model.mixin']

    # Fields based on TMF681
    content = fields.Char(string="content", help="The content of the message")
    description = fields.Char(string="description", help="Description of the message")
    log_flag = fields.Boolean(string="logFlag", help="Flag to log the message")
    message_type = fields.Char(string="messageType", help="Type of message (email, sms, etc)")
    priority = fields.Char(string="priority", help="Priority of the message")
    receiver = fields.Char(string="receiver", help="Receiver of the message")
    sender = fields.Char(string="sender", help="Sender of the message")
    state = fields.Char(string="state", help="State of the message")
    subject = fields.Char(string="subject", help="Subject of the message")
    try_times = fields.Integer(string="tryTimes", help="Number of attempts")
    attachment = fields.Char(string="attachment", help="Attachments")
    characteristic = fields.Char(string="characteristic", help="Additional characteristics")
    
    # --- MISSING FIELDS FIXED HERE ---
    scheduled_send_time = fields.Datetime(string="scheduledSendTime", help="Time when the message is scheduled to be sent")
    send_time = fields.Datetime(string="sendTime", help="Time when the message was sent")
    send_time_complete = fields.Datetime(string="sendTimeComplete", help="Time when the message sending was completed")
    # ---------------------------------

    def _get_tmf_api_path(self):
        return "/communicationMessageManagement/v4/CommunicationMessage"

    # ==========================================
    # SERIALIZATION
    # ==========================================
    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "CommunicationMessage",
            "content": self.content,
            "description": self.description,
            "logFlag": self.log_flag,
            "messageType": self.message_type,
            "priority": self.priority,
            "receiver": self.receiver,
            "sender": self.sender,
            "state": self.state,
            "subject": self.subject,
            "tryTimes": self.try_times,
            "scheduledSendTime": self.scheduled_send_time.isoformat() if self.scheduled_send_time else None,
            "sendTime": self.send_time.isoformat() if self.send_time else None,
            "sendTimeComplete": self.send_time_complete.isoformat() if self.send_time_complete else None,
            "attachment": [], # Placeholder for list
            "characteristic": [], # Placeholder for list
        }

    # ==========================================
    # NOTIFICATION LOGIC
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('communicationMessage', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('communicationMessage', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='communicationMessage',
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