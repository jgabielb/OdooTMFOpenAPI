import json
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None}


class TMFCustomer360(models.Model):
    _name = "tmf.customer360"
    _description = "TMF717 Customer360"
    _inherit = ["tmf.model.mixin"]

    customer_id = fields.Char(string="customerId")
    name = fields.Char(string="name")
    status = fields.Char(string="status")
    status_reason = fields.Char(string="statusReason")
    partner_id = fields.Many2one("res.partner", string="Customer Partner", ondelete="set null")

    engaged_party_json = fields.Text(string="engagedParty")
    customer_ref_json = fields.Text(string="customerRef")
    account_json = fields.Text(string="account")
    agreement_json = fields.Text(string="agreement")
    appointment_json = fields.Text(string="appointment")
    characteristic_json = fields.Text(string="characteristic")
    contact_medium_json = fields.Text(string="contactMedium")
    credit_profile_json = fields.Text(string="creditProfile")
    customer_bill_json = fields.Text(string="customerBill")
    interaction_item_json = fields.Text(string="interactionItem")
    loyalty_balance_json = fields.Text(string="loyaltyBalance")
    payment_method_json = fields.Text(string="paymentMethod")
    product_order_json = fields.Text(string="productOrder")
    product_value_json = fields.Text(string="productValue")
    promotion_json = fields.Text(string="promotion")
    quote_json = fields.Text(string="quote")
    recommendation_json = fields.Text(string="recommendation")
    related_party_json = fields.Text(string="relatedParty")
    service_problem_json = fields.Text(string="serviceProblem")
    trouble_ticket_json = fields.Text(string="troubleTicket")
    valid_for_json = fields.Text(string="validFor")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

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

    def _pick_partner_ref(self):
        self.ensure_one()
        # Priority: customerRef -> engagedParty -> first relatedParty item.
        for blob in (self.customer_ref_json, self.engaged_party_json):
            ref = _loads(blob)
            if isinstance(ref, dict):
                return ref
        related = _loads(self.related_party_json)
        if isinstance(related, list) and related:
            first = related[0]
            if isinstance(first, dict):
                return first
        return {}

    def _sync_partner_link(self):
        for rec in self:
            partner = rec._resolve_partner_from_ref(rec._pick_partner_ref())
            if partner:
                rec.partner_id = partner.id

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "Customer360CreateEvent",
            "update": "Customer360AttributeValueChangeEvent",
            "delete": "Customer360DeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("customer360", event_name, payload)
            except Exception:
                continue

    def _get_tmf_api_path(self):
        return "/customer360/v4/customer360"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "customerId": self.customer_id,
            "name": self.name,
            "status": self.status,
            "statusReason": self.status_reason,
            "engagedParty": _loads(self.engaged_party_json),
            "customerRef": _loads(self.customer_ref_json),
            "account": _loads(self.account_json),
            "agreement": _loads(self.agreement_json),
            "appointment": _loads(self.appointment_json),
            "characteristic": _loads(self.characteristic_json),
            "contactMedium": _loads(self.contact_medium_json),
            "creditProfile": _loads(self.credit_profile_json),
            "customerBill": _loads(self.customer_bill_json),
            "interactionItem": _loads(self.interaction_item_json),
            "loyaltyBalance": _loads(self.loyalty_balance_json),
            "paymentMethod": _loads(self.payment_method_json),
            "productOrder": _loads(self.product_order_json),
            "productValue": _loads(self.product_value_json),
            "promotion": _loads(self.promotion_json),
            "quote": _loads(self.quote_json),
            "recommendation": _loads(self.recommendation_json),
            "relatedParty": _loads(self.related_party_json),
            "serviceProblem": _loads(self.service_problem_json),
            "troubleTicket": _loads(self.trouble_ticket_json),
            "validFor": _loads(self.valid_for_json),
            "@type": self.tmf_type_value or "Customer360",
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("customerId", "customer_id"),
            ("name", "name"),
            ("status", "status"),
            ("statusReason", "status_reason"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("engagedParty", "engaged_party_json"),
            ("customerRef", "customer_ref_json"),
            ("account", "account_json"),
            ("agreement", "agreement_json"),
            ("appointment", "appointment_json"),
            ("characteristic", "characteristic_json"),
            ("contactMedium", "contact_medium_json"),
            ("creditProfile", "credit_profile_json"),
            ("customerBill", "customer_bill_json"),
            ("interactionItem", "interaction_item_json"),
            ("loyaltyBalance", "loyalty_balance_json"),
            ("paymentMethod", "payment_method_json"),
            ("productOrder", "product_order_json"),
            ("productValue", "product_value_json"),
            ("promotion", "promotion_json"),
            ("quote", "quote_json"),
            ("recommendation", "recommendation_json"),
            ("relatedParty", "related_party_json"),
            ("serviceProblem", "service_problem_json"),
            ("troubleTicket", "trouble_ticket_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_partner_link()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if (
            "customer_ref_json" in vals
            or "engaged_party_json" in vals
            or "related_party_json" in vals
            or "partner_id" in vals
        ):
            self._sync_partner_link()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res

