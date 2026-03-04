# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

TMF_API_BASE = "/tmf-api/accountManagement/v5"

RESOURCE_TO_PATH = {
    "PartyAccount": "partyAccount",
    "BillingAccount": "billingAccount",
    "FinancialAccount": "financialAccount",
    "SettlementAccount": "settlementAccount",
    "BillFormat": "billFormat",
    "BillingCycleSpecification": "billingCycleSpecification",
    "BillPresentationMedia": "billPresentationMedia",
}

IMMUTABLE_KEYS = {"id", "href", "@type", "@baseType", "@schemaLocation", "lastUpdate", "lastModified"}


def _json_loads(s, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


class TMFAccount(models.Model):
    _name = "tmf.account"
    _description = "TMF666 Account (Party/Billing/Financial/Settlement)"
    _inherit = ["tmf.model.mixin"]

    # Which TMF666 resource this record represents
    resource_type = fields.Selection(
        selection=[
            ("PartyAccount", "PartyAccount"),
            ("BillingAccount", "BillingAccount"),
            ("FinancialAccount", "FinancialAccount"),
            ("SettlementAccount", "SettlementAccount"),
        ],
        required=True,
        default="PartyAccount",
        string="@type",
    )

    # Common fields used across the account types
    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    account_type = fields.Char(string="accountType")
    state = fields.Char(string="state")
    payment_status = fields.Char(string="paymentStatus")
    rating_type = fields.Char(string="ratingType")

    # timestamps
    last_update = fields.Datetime(string="lastUpdate")

    # Complex structures stored as JSON strings
    related_party_json = fields.Text(string="relatedParty")          # array
    credit_limit_json = fields.Text(string="creditLimit")            # object
    account_balance_json = fields.Text(string="accountBalance")      # array
    account_relationship_json = fields.Text(string="accountRelationship")  # array
    contact_json = fields.Text(string="contact")                     # array
    tax_exemption_json = fields.Text(string="taxExemption")          # array
    financial_account_json = fields.Text(string="financialAccount")  # ref object
    bill_structure_json = fields.Text(string="billStructure")        # object
    default_payment_method_json = fields.Text(string="defaultPaymentMethod")  # ref object
    payment_plan_json = fields.Text(string="paymentPlan")            # array
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        related = _json_loads(self.related_party_json, [])
        if not isinstance(related, list):
            related = [related] if related else []
        env = self.env["res.partner"].sudo()
        for party in related:
            if not isinstance(party, dict):
                continue
            rid = party.get("id")
            if rid:
                partner = env.search([("tmf_id", "=", str(rid))], limit=1)
                if partner:
                    return partner
                if str(rid).isdigit():
                    partner = env.browse(int(rid))
                    if partner.exists():
                        return partner
            name = (party.get("name") or "").strip()
            if name:
                partner = env.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _sync_partner_link(self):
        for rec in self:
            partner = rec._resolve_partner_from_related_party()
            if partner:
                rec.partner_id = partner.id

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "AccountCreateEvent",
            "update": "AccountAttributeValueChangeEvent",
            "delete": "AccountDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("account", event_name, payload)
            except Exception:
                continue

    def _resource_path(self):
        return RESOURCE_TO_PATH.get(self.resource_type, "partyAccount")

    def _href_for(self):
        rid = self.tmf_id or str(self.id)
        return f"{TMF_API_BASE}/{self._resource_path()}/{rid}"

    def to_tmf_json(self):
        self.ensure_one()

        # IMPORTANT: never return description=False (breaks CTK schema "must be string")
        desc = self.description if self.description else None

        payload = {
            "@type": self.resource_type,
            "id": self.tmf_id or str(self.id),
            "href": self._href_for(),
            "name": self.name,
            "description": desc,
            "accountType": self.account_type if self.account_type else None,
            "state": self.state if self.state else None,
            "paymentStatus": self.payment_status if self.payment_status else None,
            "ratingType": self.rating_type if self.rating_type else None,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "relatedParty": _json_loads(self.related_party_json, []),
            "creditLimit": _json_loads(self.credit_limit_json, None),
            "accountBalance": _json_loads(self.account_balance_json, []),
            "accountRelationship": _json_loads(self.account_relationship_json, []),
            "contact": _json_loads(self.contact_json, []),
            "taxExemption": _json_loads(self.tax_exemption_json, []),
            "financialAccount": _json_loads(self.financial_account_json, None),
            "billStructure": _json_loads(self.bill_structure_json, None),
            "defaultPaymentMethod": _json_loads(self.default_payment_method_json, None),
            "paymentPlan": _json_loads(self.payment_plan_json, []),
        }

        return {k: v for k, v in payload.items() if v not in (None, [], "")}

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        patched = []
        for vals in vals_list:
            new_vals = dict(vals)
            new_vals["last_update"] = now
            patched.append(new_vals)
        recs = super().create(patched)
        recs._sync_partner_link()
        recs._notify("create")
        return recs

    def write(self, vals):
        vals = dict(vals)
        vals["last_update"] = fields.Datetime.now()
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# -----------------------------
# TMF666 BillFormat
# -----------------------------
class TMFBillFormat(models.Model):
    _name = "tmf.bill.format"
    _description = "TMF666 BillFormat"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    last_update = fields.Datetime(string="lastUpdate")

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "AccountCreateEvent",
            "update": "AccountAttributeValueChangeEvent",
            "delete": "AccountDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("account", event_name, payload)
            except Exception:
                continue

    def _href_for(self):
        rid = self.tmf_id or str(self.id)
        return f"{TMF_API_BASE}/billFormat/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "@type": "BillFormat",
            "id": self.tmf_id or str(self.id),
            "href": self._href_for(),
            "name": self.name,
            "description": self.description if self.description else None,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
        }
        return {k: v for k, v in payload.items() if v not in (None, [], "")}

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        patched = []
        for vals in vals_list:
            new_vals = dict(vals)
            new_vals["last_update"] = now
            patched.append(new_vals)
        recs = super().create(patched)
        recs._notify("create")
        return recs

    def write(self, vals):
        vals = dict(vals)
        vals["last_update"] = fields.Datetime.now()
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# -----------------------------
# TMF666 BillingCycleSpecification
# -----------------------------
class TMFBillingCycleSpecification(models.Model):
    _name = "tmf.billing.cycle.spec"
    _description = "TMF666 BillingCycleSpecification"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")

    frequency = fields.Char(string="frequency")
    billing_period = fields.Char(string="billingPeriod")
    billing_date_shift = fields.Integer(string="billingDateShift")
    charge_date_offset = fields.Integer(string="chargeDateOffset")
    credit_date_offset = fields.Integer(string="creditDateOffset")
    mailing_date_offset = fields.Integer(string="mailingDateOffset")
    payment_due_date_offset = fields.Integer(string="paymentDueDateOffset")

    valid_for_json = fields.Text(string="validFor")  # TimePeriod object
    last_update = fields.Datetime(string="lastUpdate")

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "AccountCreateEvent",
            "update": "AccountAttributeValueChangeEvent",
            "delete": "AccountDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("account", event_name, payload)
            except Exception:
                continue

    def _href_for(self):
        rid = self.tmf_id or str(self.id)
        return f"{TMF_API_BASE}/billingCycleSpecification/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "@type": "BillingCycleSpecification",
            "id": self.tmf_id or str(self.id),
            "href": self._href_for(),
            "name": self.name,
            "description": self.description if self.description else None,
            "frequency": self.frequency if self.frequency else None,
            "billingPeriod": self.billing_period if self.billing_period else None,
            "billingDateShift": self.billing_date_shift,
            "chargeDateOffset": self.charge_date_offset,
            "creditDateOffset": self.credit_date_offset,
            "mailingDateOffset": self.mailing_date_offset,
            "paymentDueDateOffset": self.payment_due_date_offset,
            "validFor": _json_loads(self.valid_for_json, None),
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
        }
        return {k: v for k, v in payload.items() if v not in (None, [], "")}

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        patched = []
        for vals in vals_list:
            new_vals = dict(vals)
            new_vals["last_update"] = now
            patched.append(new_vals)
        recs = super().create(patched)
        recs._notify("create")
        return recs

    def write(self, vals):
        vals = dict(vals)
        vals["last_update"] = fields.Datetime.now()
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# -----------------------------
# TMF666 BillPresentationMedia
# -----------------------------
class TMFBillPresentationMedia(models.Model):
    _name = "tmf.bill.presentation.media"
    _description = "TMF666 BillPresentationMedia"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    last_update = fields.Datetime(string="lastUpdate")

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "AccountCreateEvent",
            "update": "AccountAttributeValueChangeEvent",
            "delete": "AccountDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("account", event_name, payload)
            except Exception:
                continue

    def _href_for(self):
        rid = self.tmf_id or str(self.id)
        return f"{TMF_API_BASE}/billPresentationMedia/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "@type": "BillPresentationMedia",
            "id": self.tmf_id or str(self.id),
            "href": self._href_for(),
            "name": self.name,
            "description": self.description if self.description else None,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
        }
        return {k: v for k, v in payload.items() if v not in (None, [], "")}

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        patched = []
        for vals in vals_list:
            new_vals = dict(vals)
            new_vals["last_update"] = now
            patched.append(new_vals)
        recs = super().create(patched)
        recs._notify("create")
        return recs

    def write(self, vals):
        vals = dict(vals)
        vals["last_update"] = fields.Datetime.now()
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
