#!/usr/bin/env python3
"""Generate reverse-bridge addons: Odoo native → TMF model sync."""
import os, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))

BRIDGES = [
    {
        "addon": "tmf_bridge_project",
        "summary": "Bridge: Odoo Project ↔ TMF Work Management",
        "depends": ["project", "tmf_work_management"],
        "odoo_model": "project.task",
        "tmf_model": "tmf.work",
        "odoo_model_under": "project_task",
        "tmf_link_field": "project_task_id",
        "reverse_field": "tmf_work_id",
        "reverse_field_label": "TMF Work",
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging

            _logger = logging.getLogger(__name__)


            class ProjectTaskTMF(models.Model):
                _inherit = "project.task"

                tmf_work_id = fields.Many2one(
                    "tmf.work", string="TMF Work",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_work(self):
                    Work = self.env["tmf.work"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        vals = {
                            "name": rec.name or "Untitled",
                            "description": rec.description or "",
                            "state": self._map_stage_to_tmf(rec),
                            "partner_id": rec.partner_id.id if rec.partner_id else False,
                        }
                        if rec.tmf_work_id and rec.tmf_work_id.exists():
                            rec.tmf_work_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        work = Work.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_work_id": work.id})
                        if hasattr(work, "project_task_id"):
                            work.with_context(skip_tmf_bridge=True).write({"project_task_id": rec.id})

                @staticmethod
                def _map_stage_to_tmf(rec):
                    if not rec.stage_id:
                        return "acknowledged"
                    name = (rec.stage_id.name or "").lower()
                    if "new" in name or "draft" in name:
                        return "acknowledged"
                    if "progress" in name or "open" in name:
                        return "inProgress"
                    if "done" in name or "close" in name or "complete" in name:
                        return "completed"
                    if "cancel" in name:
                        return "cancelled"
                    return "inProgress"

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_tmf_work()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on project.task create", exc_info=True)
                    return recs

                def write(self, vals):
                    res = super().write(vals)
                    trigger = {"name", "description", "partner_id", "stage_id"}
                    if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
                        try:
                            self._sync_tmf_work()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on project.task write", exc_info=True)
                    return res
        """),
    },
    {
        "addon": "tmf_bridge_stock",
        "summary": "Bridge: Odoo Stock Picking ↔ TMF Shipment",
        "depends": ["stock", "tmf_shipment_management"],
        "odoo_model": "stock.picking",
        "tmf_model": "tmf.shipment",
        "odoo_model_under": "stock_picking",
        "tmf_link_field": "picking_id",
        "reverse_field": "tmf_shipment_id",
        "reverse_field_label": "TMF Shipment",
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging

            _logger = logging.getLogger(__name__)


            class StockPickingTMF(models.Model):
                _inherit = "stock.picking"

                tmf_shipment_id = fields.Many2one(
                    "tmf.shipment", string="TMF Shipment",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_shipment(self):
                    Shipment = self.env["tmf.shipment"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        vals = {
                            "name": rec.name or "Untitled",
                            "description": rec.note or "",
                            "state": self._map_state_to_tmf(rec),
                            "partner_id": rec.partner_id.id if rec.partner_id else False,
                        }
                        if rec.tmf_shipment_id and rec.tmf_shipment_id.exists():
                            rec.tmf_shipment_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        shipment = Shipment.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_shipment_id": shipment.id})
                        if hasattr(shipment, "picking_id"):
                            shipment.with_context(skip_tmf_bridge=True).write({"picking_id": rec.id})

                @staticmethod
                def _map_state_to_tmf(rec):
                    mapping = {
                        "draft": "initialized",
                        "waiting": "acknowledged",
                        "confirmed": "acknowledged",
                        "assigned": "inProgress",
                        "done": "completed",
                        "cancel": "cancelled",
                    }
                    return mapping.get(rec.state, "acknowledged")

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_tmf_shipment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on stock.picking create", exc_info=True)
                    return recs

                def write(self, vals):
                    res = super().write(vals)
                    trigger = {"name", "note", "partner_id", "state"}
                    if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
                        try:
                            self._sync_tmf_shipment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on stock.picking write", exc_info=True)
                    return res
        """),
    },
    {
        "addon": "tmf_bridge_payment",
        "summary": "Bridge: Odoo Payment ↔ TMF Payment",
        "depends": ["account", "tmf_payment"],
        "odoo_model": "account.payment",
        "tmf_model": "tmf.payment",
        "odoo_model_under": "account_payment",
        "tmf_link_field": "account_payment_id",
        "reverse_field": "tmf_payment_id",
        "reverse_field_label": "TMF Payment",
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import json
            import logging

            _logger = logging.getLogger(__name__)


            class AccountPaymentTMF(models.Model):
                _inherit = "account.payment"

                tmf_payment_id = fields.Many2one(
                    "tmf.payment", string="TMF Payment",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_payment(self):
                    Payment = self.env["tmf.payment"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        total_amount = json.dumps({
                            "unit": rec.currency_id.name or "USD",
                            "value": rec.amount,
                        })
                        account_ref = json.dumps({
                            "id": str(rec.partner_id.id) if rec.partner_id else "0",
                            "name": rec.partner_id.name if rec.partner_id else "Unknown",
                            "@referredType": "BillingAccount",
                        })
                        vals = {
                            "name": rec.name or "Payment",
                            "description": rec.ref or rec.name or "",
                            "status": self._map_state_to_tmf(rec),
                            "partner_id": rec.partner_id.id if rec.partner_id else False,
                            "total_amount_json": total_amount,
                            "account_json": account_ref,
                            "payment_date": rec.date,
                        }
                        if rec.tmf_payment_id and rec.tmf_payment_id.exists():
                            rec.tmf_payment_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        tmf_pay = Payment.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_payment_id": tmf_pay.id})
                        if hasattr(tmf_pay, "account_payment_id"):
                            tmf_pay.with_context(skip_tmf_bridge=True).write({"account_payment_id": rec.id})

                @staticmethod
                def _map_state_to_tmf(rec):
                    state = getattr(rec, "state", "") or ""
                    mapping = {
                        "draft": "pendingAuthorization",
                        "posted": "approved",
                        "sent": "approved",
                        "reconciled": "approved",
                        "cancelled": "declined",
                        "cancel": "declined",
                    }
                    return mapping.get(state, "pendingAuthorization")

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_tmf_payment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on account.payment create", exc_info=True)
                    return recs

                def write(self, vals):
                    res = super().write(vals)
                    trigger = {"name", "ref", "partner_id", "amount", "state", "date"}
                    if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
                        try:
                            self._sync_tmf_payment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on account.payment write", exc_info=True)
                    return res
        """),
    },
    {
        "addon": "tmf_bridge_calendar",
        "summary": "Bridge: Odoo Calendar ↔ TMF Appointment",
        "depends": ["calendar", "tmf_appointment"],
        "odoo_model": "calendar.event",
        "tmf_model": "tmf.appointment",
        "odoo_model_under": "calendar_event",
        "tmf_link_field": "calendar_event_id",
        "reverse_field": "tmf_appointment_id",
        "reverse_field_label": "TMF Appointment",
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging

            _logger = logging.getLogger(__name__)


            class CalendarEventTMF(models.Model):
                _inherit = "calendar.event"

                tmf_appointment_id = fields.Many2one(
                    "tmf.appointment", string="TMF Appointment",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_appointment(self):
                    Appt = self.env["tmf.appointment"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        partner = rec.partner_ids[:1] if rec.partner_ids else self.env["res.partner"]
                        vals = {
                            "category": rec.categ_ids[:1].name if rec.categ_ids else "General",
                            "description": rec.description or rec.name or "",
                            "status": "confirmed" if rec.active else "cancelled",
                            "valid_for_start": rec.start,
                            "valid_for_end": rec.stop,
                            "partner_id": partner.id if partner else False,
                        }
                        if rec.tmf_appointment_id and rec.tmf_appointment_id.exists():
                            rec.tmf_appointment_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        appt = Appt.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_appointment_id": appt.id})
                        if hasattr(appt, "calendar_event_id"):
                            appt.with_context(skip_tmf_bridge=True).write({"calendar_event_id": rec.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_tmf_appointment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on calendar.event create", exc_info=True)
                    return recs

                def write(self, vals):
                    res = super().write(vals)
                    trigger = {"name", "description", "start", "stop", "partner_ids", "categ_ids", "active"}
                    if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
                        try:
                            self._sync_tmf_appointment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on calendar.event write", exc_info=True)
                    return res
        """),
    },
    {
        "addon": "tmf_bridge_mail",
        "summary": "Bridge: Odoo Mail ↔ TMF Communication Message",
        "depends": ["mail", "tmf_communication_message"],
        "odoo_model": "mail.message",
        "tmf_model": "tmf.communication.message",
        "odoo_model_under": "mail_message",
        "tmf_link_field": None,
        "reverse_field": "tmf_comm_message_id",
        "reverse_field_label": "TMF Communication Message",
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import json
            import logging

            _logger = logging.getLogger(__name__)


            class MailMessageTMF(models.Model):
                _inherit = "mail.message"

                tmf_comm_message_id = fields.Many2one(
                    "tmf.communication.message", string="TMF Communication Message",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_comm_message(self):
                    Msg = self.env["tmf.communication.message"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        if rec.message_type not in ("email", "comment"):
                            continue
                        sender = {}
                        if rec.author_id:
                            sender = {"id": str(rec.author_id.id), "name": rec.author_id.name}
                        receiver = []
                        for p in rec.partner_ids:
                            receiver.append({"id": str(p.id), "name": p.name})
                        if not receiver:
                            continue
                        vals = {
                            "content": rec.body or rec.subject or "",
                            "message_type": "email" if rec.message_type == "email" else "sms",
                            "subject": rec.subject or "",
                            "sender": sender,
                            "receiver": receiver,
                            "partner_id": rec.author_id.id if rec.author_id else False,
                            "state": "completed",
                        }
                        if rec.tmf_comm_message_id and rec.tmf_comm_message_id.exists():
                            rec.tmf_comm_message_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        msg = Msg.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_comm_message_id": msg.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_tmf_comm_message()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on mail.message create", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_address",
        "summary": "Bridge: Odoo Partner Address ↔ TMF Geographic Address",
        "depends": ["base", "tmf_geographic_address"],
        "odoo_model": "res.partner",
        "tmf_model": "tmf.geographic.address",
        "odoo_model_under": "res_partner",
        "tmf_link_field": "partner_id",
        "reverse_field": "tmf_geographic_address_id",
        "reverse_field_label": "TMF Geographic Address",
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging

            _logger = logging.getLogger(__name__)


            class ResPartnerTMFAddress(models.Model):
                _inherit = "res.partner"

                tmf_geographic_address_id = fields.Many2one(
                    "tmf.geographic.address", string="TMF Geographic Address",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_geographic_address(self):
                    Addr = self.env["tmf.geographic.address"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        if not any([rec.street, rec.city, rec.zip, rec.country_id]):
                            continue
                        vals = {
                            "street_name": rec.street or "",
                            "street_nr": rec.street2 or "",
                            "city": rec.city or "",
                            "postcode": rec.zip or "",
                            "state_or_province": rec.state_id.name if rec.state_id else "",
                            "country": rec.country_id.name if rec.country_id else "",
                            "name": f"{rec.street or ''}, {rec.city or ''}".strip(", "),
                            "partner_id": rec.id,
                        }
                        if rec.tmf_geographic_address_id and rec.tmf_geographic_address_id.exists():
                            rec.tmf_geographic_address_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        addr = Addr.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_geographic_address_id": addr.id})

                def write(self, vals):
                    res = super().write(vals)
                    trigger = {"street", "street2", "city", "zip", "state_id", "country_id"}
                    if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
                        try:
                            self._sync_tmf_geographic_address()
                        except Exception:
                            _logger.warning("TMF bridge sync failed on res.partner address write", exc_info=True)
                    return res
        """),
    },
]


def gen_manifest(b):
    deps = ", ".join(f'"{d}"' for d in b["depends"])
    return f'''# -*- coding: utf-8 -*-
{{
    "name": "{b['summary']}",
    "version": "17.0.1.0.0",
    "category": "TMF/Bridge",
    "summary": "{b['summary']}",
    "depends": [{deps}],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}}
'''


def gen_security(b):
    addon = b["addon"]
    odoo_under = b["odoo_model"].replace(".", "_")
    return f"id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"


def main():
    ok = 0
    for b in BRIDGES:
        addon_dir = os.path.join(ROOT, b["addon"])
        models_dir = os.path.join(addon_dir, "models")
        security_dir = os.path.join(addon_dir, "security")
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(security_dir, exist_ok=True)

        # __manifest__.py
        with open(os.path.join(addon_dir, "__manifest__.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(gen_manifest(b))

        # __init__.py (root)
        with open(os.path.join(addon_dir, "__init__.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write("from . import models\n")

        # models/__init__.py
        with open(os.path.join(models_dir, "__init__.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write("from . import main\n")

        # models/main.py
        with open(os.path.join(models_dir, "main.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(b["model_file"])

        # security/ir.model.access.csv (empty — we inherit existing models, no new ones)
        with open(os.path.join(security_dir, "ir.model.access.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n")

        print(f"  OK: {b['addon']}")
        ok += 1

    print(f"\n=== {ok} bridge addons generated ===")


if __name__ == "__main__":
    main()
