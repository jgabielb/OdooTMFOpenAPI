# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


def _dt_to_iso_z(dtval):
    """Return ISO-8601 with Z (UTC-ish) as CTK commonly expects."""
    if not dtval:
        return None
    if isinstance(dtval, str):
        # assume already iso
        return dtval
    if isinstance(dtval, datetime):
        return dtval.replace(microsecond=0).isoformat() + "Z"
    return str(dtval)


class TMFCommunicationMessage(models.Model):
    _name = "tmf.communication.message"
    _description = "TMF681 CommunicationMessage"
    _inherit = ["tmf.model.mixin"]
    _rec_name = "tmf_id"

    # ---------------------------
    # Mandatory by TMF681 conformance (POST input)
    # content, messageType, receiver, sender
    # ---------------------------
    content = fields.Char(string="content", required=True, help="The content of the message")  # M
    message_type = fields.Char(string="messageType", required=True, help="Type of message (email, sms, etc)")  # M

    # receiver MUST be an array (Array of Receiver)
    receiver = fields.Json(string="receiver", required=True, default=list, help="Array of Receiver objects")  # M

    # sender is mandatory (object)
    sender = fields.Json(string="sender", required=True, default=dict, help="Sender object")  # M
    partner_id = fields.Many2one("res.partner", string="Sender Partner", ondelete="set null")

    # ---------------------------
    # Optional fields (not mandated by TMF681 conformance profile)
    # ---------------------------
    description = fields.Char(string="description", help="Description of the message")
    log_flag = fields.Boolean(string="logFlag", help="Flag to log the message")
    priority = fields.Char(string="priority", help="Priority of the message")
    state = fields.Char(string="state", help="State of the message")
    subject = fields.Char(string="subject", help="Subject of the message")
    try_times = fields.Integer(string="tryTimes", help="Number of attempts")

    # Typically arrays/complex objects -> JSON
    attachment = fields.Json(string="attachment", default=list, help="Attachments array (if used)")
    characteristic = fields.Json(string="characteristic", default=list, help="Array of Characteristic objects")

    scheduled_send_time = fields.Datetime(string="scheduledSendTime")
    send_time = fields.Datetime(string="sendTime")
    send_time_complete = fields.Datetime(string="sendTimeComplete")

    # ------------------------------------------------------------
    # API path helper (if your mixin uses it)
    # ------------------------------------------------------------
    def _get_tmf_api_path(self):
        # Your controller is using /tmf-api/communicationManagement/v4/communicationMessage
        # Keep this aligned with your routing/base; adjust if your mixin builds href from it.
        return "/tmf-api/communicationManagement/v4/communicationMessage"

    def _resolve_partner_from_ref(self, ref):
        if not isinstance(ref, dict):
            return False
        env_partner = self.env["res.partner"].sudo()
        rid = ref.get("id")
        if rid:
            partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
            if partner:
                return partner
            if str(rid).isdigit():
                partner = env_partner.browse(int(rid))
                if partner.exists():
                    return partner
        name = (ref.get("name") or "").strip()
        if name:
            return env_partner.search([("name", "=", name)], limit=1)
        return False

    def _sync_sender_partner(self):
        for rec in self:
            partner = rec._resolve_partner_from_ref(rec.sender or {})
            if partner:
                rec.partner_id = partner.id

    # ------------------------------------------------------------
    # Validation to keep CTK happy and align with conformance rules
    # - receiver: list
    # - characteristic: if present, list of objects w/ name+value
    # ------------------------------------------------------------
    @api.constrains("receiver", "sender", "characteristic")
    def _check_tmf681_shapes(self):
        for rec in self:
            # receiver must be array
            if rec.receiver is None or not isinstance(rec.receiver, list) or len(rec.receiver) == 0:
                raise ValidationError("TMF681: 'receiver' must be a non-empty array.")

            # sender must be object
            if rec.sender is None or not isinstance(rec.sender, dict) or len(rec.sender.keys()) == 0:
                raise ValidationError("TMF681: 'sender' must be a non-empty object.")

            # characteristic optional; if present enforce items
            if rec.characteristic:
                if not isinstance(rec.characteristic, list):
                    raise ValidationError("TMF681: 'characteristic' must be an array when present.")
                for ch in rec.characteristic:
                    if not isinstance(ch, dict):
                        raise ValidationError("TMF681: each 'characteristic' item must be an object.")
                    if not ch.get("name") or ch.get("value") is None:
                        raise ValidationError("TMF681: characteristic items must include 'name' and 'value'.")

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------
    def to_tmf_json(self, host_url="", fields_filter=None):
        """
        Conformance:
        - Response must include id + href (in response messages)
        - Mandatory attributes should be present when no ?fields= selection is used
        - fields_filter applies only to first-level attributes (we keep id/href/@type always)
        """
        self.ensure_one()

        host_url = (host_url or "").rstrip("/")
        api_path = self._get_tmf_api_path().rstrip("/")
        tmf_id = getattr(self, "tmf_id", None) or str(self.id)

        href = getattr(self, "href", None)
        if not href:
            href = f"{host_url}{api_path}/{tmf_id}" if host_url else f"{api_path}/{tmf_id}"

        payload = {
            "id": tmf_id,
            "href": href,
            "@type": "CommunicationMessage",

            # Mandatory
            "content": self.content,
            "messageType": self.message_type,
            "receiver": self.receiver or [],
            "sender": self.sender or {},

            # Optional
            "description": self.description,
            "logFlag": bool(self.log_flag) if self.log_flag is not None else False,
            "priority": self.priority,
            "state": self.state,
            "subject": self.subject,
            "tryTimes": self.try_times,
            "scheduledSendTime": _dt_to_iso_z(self.scheduled_send_time),
            "sendTime": _dt_to_iso_z(self.send_time),
            "sendTimeComplete": _dt_to_iso_z(self.send_time_complete),
            "attachment": self.attachment or [],
            "characteristic": self.characteristic or [],
        }

        # Apply top-level field selection (?fields=)
        if fields_filter:
            allowed = {f.strip() for f in fields_filter.split(",") if f.strip()}
            # Always preserve identifiers + @type
            allowed |= {"id", "href", "@type"}
            payload = {k: v for k, v in payload.items() if k in allowed}

        return payload

    # ------------------------------------------------------------
    # Notifications (same as yours, kept)
    # ------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_sender_partner()
        for rec in recs:
            rec._notify("communicationMessage", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "sender" in vals or "partner_id" in vals:
            self._sync_sender_partner()
        for rec in self:
            rec._notify("communicationMessage", "update", rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="communicationMessage",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
