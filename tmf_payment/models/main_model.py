from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import uuid
from datetime import datetime

API_BASE = "/tmf-api/paymentManagement/v4"

def _iso_z(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.replace(microsecond=0).isoformat() + "Z"
    return str(dt)

def _json_load(val):
    if not val:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            # keep as string if it isn't JSON
            return val
    return val

def _json_dump(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)

class TMFPayment(models.Model):
    _name = "tmf.payment"
    _description = "TMF676 Payment"
    _inherit = ["tmf.model.mixin"]

    # TMF core identifiers (assuming tmf.model.mixin provides tmf_id + href)
    # If your mixin doesn't generate tmf_id/href, we can add it here.

    # Optional informational fields
    authorization_code = fields.Char(string="authorizationCode")
    correlator_id = fields.Char(string="correlatorId")
    description = fields.Char(string="description")
    name = fields.Char(string="name")
    payment_date = fields.Datetime(string="paymentDate")
    status = fields.Char(string="status")
    status_date = fields.Datetime(string="statusDate")
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    account_payment_id = fields.Many2one("account.payment", string="Odoo Payment", ondelete="set null")
    invoice_ids = fields.Many2many("account.move", "tmf_payment_invoice_rel", "tmf_payment_id", "move_id", string="Invoices")
    payment_method_line_id = fields.Many2one("account.payment.method.line", string="Odoo Payment Method", ondelete="set null")
    journal_id = fields.Many2one("account.journal", string="Journal", ondelete="set null")

    # TMF structured fields stored as JSON strings
    account_json = fields.Text(string="account")            # expects {"id": "...", ...}
    total_amount_json = fields.Text(string="totalAmount")   # expects {"unit": "...", "value": ...}
    payment_method_json = fields.Text(string="paymentMethod")  # ref or value object
    channel_json = fields.Text(string="channel")            # if present => {"id": "...", ...}
    payment_item_json = fields.Text(string="paymentItem")   # if present => [ { "item": { "id": "..." } ... } ]

    def _resolve_partner_from_account_json(self):
        self.ensure_one()
        account = _json_load(self.account_json)
        if not isinstance(account, dict):
            return self.env["res.partner"]
        pid = account.get("id")
        if not pid:
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
        if not partner and str(pid).isdigit():
            partner = Partner.browse(int(pid))
        if partner and partner.exists():
            return partner
        return self.env["res.partner"]

    def _resolve_invoices_from_payment_item_json(self):
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        invoices = Move.browse()
        items = _json_load(self.payment_item_json)
        if not isinstance(items, list):
            return invoices
        for item in items:
            if not isinstance(item, dict):
                continue
            ref = item.get("item")
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if not rid:
                continue
            move = Move.search([("tmf_id", "=", str(rid))], limit=1)
            if not move and str(rid).isdigit():
                move = Move.browse(int(rid))
            if move and move.exists():
                invoices |= move
        return invoices

    def _resolve_payment_method_line(self):
        self.ensure_one()
        if self.payment_method_line_id and self.payment_method_line_id.exists():
            return self.payment_method_line_id
        method_obj = _json_load(self.payment_method_json)
        if not isinstance(method_obj, dict):
            return self.env["account.payment.method.line"]
        pm_id = method_obj.get("id")
        if not pm_id:
            return self.env["account.payment.method.line"]
        tmf_pm = self.env["tmf.payment.method"].sudo().search([("tmf_id", "=", str(pm_id))], limit=1)
        if tmf_pm and tmf_pm.payment_method_line_id and tmf_pm.payment_method_line_id.exists():
            return tmf_pm.payment_method_line_id
        return self.env["account.payment.method.line"]

    def _sync_account_payment(self):
        AccountPayment = self.env["account.payment"].sudo()
        Journal = self.env["account.journal"].sudo()
        for rec in self:
            partner = rec.partner_id or rec._resolve_partner_from_account_json()
            if partner and partner.exists() and rec.partner_id != partner:
                rec.partner_id = partner.id

            invoices = rec.invoice_ids or rec._resolve_invoices_from_payment_item_json()
            if invoices:
                rec.invoice_ids = [(6, 0, invoices.ids)]

            total = _json_load(rec.total_amount_json) or {}
            amount = 0.0
            if isinstance(total, dict):
                try:
                    amount = float(total.get("value") or 0.0)
                except Exception:
                    amount = 0.0

            method_line = rec._resolve_payment_method_line()
            journal = rec.journal_id
            if not journal:
                if method_line and method_line.exists() and method_line.journal_id:
                    journal = method_line.journal_id
                else:
                    journal = Journal.search([("type", "in", ["bank", "cash"])], limit=1)
                if journal:
                    rec.journal_id = journal.id
            if method_line and method_line.exists() and rec.payment_method_line_id != method_line:
                rec.payment_method_line_id = method_line.id

            if not partner or not partner.exists() or not journal:
                continue

            pay_vals = {
                "partner_type": "customer",
                "payment_type": "inbound",
                "partner_id": partner.id,
                "amount": amount,
                "date": (rec.payment_date.date() if rec.payment_date else fields.Date.context_today(rec)),
                "journal_id": journal.id,
            }
            if method_line and method_line.exists():
                pay_vals["payment_method_line_id"] = method_line.id

            if rec.account_payment_id and rec.account_payment_id.exists():
                if rec.account_payment_id.state == "draft":
                    rec.account_payment_id.write(pay_vals)
            else:
                rec.account_payment_id = AccountPayment.create(pay_vals).id

    def _notify(self, action):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PaymentCreateEvent",
            "update": "PaymentAttributeValueChangeEvent",
            "delete": "PaymentDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        for rec in self:
            try:
                host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
                hub._notify_subscribers("payment", event_name, rec.to_tmf_json(host_url=host_url))
            except Exception:
                continue

    def _get_tmf_api_path(self):
        # IMPORTANT: conformance uses /payment in the description; base path is per your gateway.
        # We'll expose routes as /payment in controller and build href accordingly.
        return "/paymentManagement/v4/payment"

    def _build_href(self, host_url=""):
        host_url = (host_url or "").rstrip("/")
        return f"{host_url}{API_BASE}/payment/{self.tmf_id}"

    def to_tmf_json(self, host_url="", fields_filter=None):
        self.ensure_one()

        account_obj = _json_load(self.account_json)
        if not account_obj and self.partner_id:
            account_obj = {
                "id": str(self.partner_id.tmf_id or self.partner_id.id),
                "name": self.partner_id.name,
                "@referredType": "Customer",
            }
        payment_item_obj = _json_load(self.payment_item_json)
        if not payment_item_obj and self.invoice_ids:
            payment_item_obj = [{
                "item": {
                    "id": str(m.tmf_id or m.id),
                    "name": m.name,
                    "@referredType": "CustomerBill",
                }
            } for m in self.invoice_ids]
        status_value = self.status
        if not status_value and self.account_payment_id:
            status_value = self.account_payment_id.state

        obj = {
            "id": self.tmf_id,
            "href": self._build_href(host_url),
            "@type": "Payment",
            "authorizationCode": self.authorization_code,
            "correlatorId": self.correlator_id,
            "description": self.description,
            "name": self.name,
            "paymentDate": _iso_z(self.payment_date),
            "status": status_value,
            "statusDate": _iso_z(self.status_date),
            "account": account_obj,
            "totalAmount": _json_load(self.total_amount_json),
            "paymentMethod": _json_load(self.payment_method_json) or {"name": "unspecified", "@type": "PaymentMethodRef"},
            "channel": _json_load(self.channel_json),
            "paymentItem": payment_item_obj,
        }

        # drop nulls
        obj = {k: v for k, v in obj.items() if v is not None}

        # apply fields selection (top-level only)
        if fields_filter:
            allowed = set(f.strip() for f in fields_filter.split(",") if f.strip())
            allowed.update({"id", "href"})  # force for CTK
            obj = {k: v for k, v in obj.items() if k in allowed}

        return self._tmf_normalize_payload(obj)

    @api.constrains("account_json", "total_amount_json", "payment_method_json", "channel_json", "payment_item_json")
    def _check_conformance_rules(self):
        for rec in self:
            account = _json_load(rec.account_json)
            if not isinstance(account, dict) or not account.get("id"):
                raise ValidationError("TMF676: 'account.id' is mandatory for Payment (POST).")

            total = _json_load(rec.total_amount_json)
            if not isinstance(total, dict) or total.get("unit") in (None, "") or total.get("value") in (None, ""):
                raise ValidationError("TMF676: 'totalAmount.unit' and 'totalAmount.value' are mandatory.")

            pm = _json_load(rec.payment_method_json)
            if not isinstance(pm, dict):
                raise ValidationError("TMF676: 'paymentMethod' is mandatory and must be an object.")
            pm_type = pm.get("@type")
            if pm_type == "paymentMethodRef":
                if not pm.get("id") or not pm.get("@referredType"):
                    raise ValidationError("TMF676: paymentMethodRef requires 'id' and '@referredType'.")

            ch = _json_load(rec.channel_json)
            if ch is not None:
                if not isinstance(ch, dict) or not ch.get("id"):
                    raise ValidationError("TMF676: if 'channel' is present, 'channel.id' is mandatory.")

            items = _json_load(rec.payment_item_json)
            if items is not None:
                if not isinstance(items, list):
                    raise ValidationError("TMF676: 'paymentItem' must be an array if present.")
                for it in items:
                    if not isinstance(it, dict):
                        raise ValidationError("TMF676: each paymentItem entry must be an object.")
                    item_obj = it.get("item")
                    if not isinstance(item_obj, dict) or not item_obj.get("id"):
                        raise ValidationError("TMF676: paymentItem.item.id is mandatory if paymentItem is present.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get("partner_id")
            if partner_id and not vals.get("account_json"):
                partner = self.env["res.partner"].sudo().browse(partner_id)
                if partner and partner.exists():
                    vals["account_json"] = _json_dump({
                        "id": str(partner.tmf_id or partner.id),
                        "name": partner.name,
                        "@referredType": "Customer",
                    })
        recs = super().create(vals_list)
        recs._sync_account_payment()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._sync_account_payment()
        self._notify("update")
        return res

    def unlink(self):
        host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
        payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        hub = self.env["tmf.hub.subscription"].sudo()
        res = super().unlink()
        for payload in payloads:
            try:
                hub._notify_subscribers("payment", "PaymentDeleteEvent", payload)
            except Exception:
                continue
        return res
