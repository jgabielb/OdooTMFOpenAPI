import json
from odoo import fields, models


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
        return _compact(payload)

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
