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

    # TMF structured fields stored as JSON strings
    account_json = fields.Text(string="account")            # expects {"id": "...", ...}
    total_amount_json = fields.Text(string="totalAmount")   # expects {"unit": "...", "value": ...}
    payment_method_json = fields.Text(string="paymentMethod")  # ref or value object
    channel_json = fields.Text(string="channel")            # if present => {"id": "...", ...}
    payment_item_json = fields.Text(string="paymentItem")   # if present => [ { "item": { "id": "..." } ... } ]

    def _get_tmf_api_path(self):
        # IMPORTANT: conformance uses /payment in the description; base path is per your gateway.
        # We'll expose routes as /payment in controller and build href accordingly.
        return "/paymentManagement/v4/payment"

    def _build_href(self, host_url=""):
        host_url = (host_url or "").rstrip("/")
        return f"{host_url}{API_BASE}/payment/{self.tmf_id}"

    def to_tmf_json(self, host_url="", fields_filter=None):
        self.ensure_one()

        obj = {
            "id": self.tmf_id,
            "href": self._build_href(host_url),
            "@type": "Payment",
            "authorizationCode": self.authorization_code,
            "correlatorId": self.correlator_id,
            "description": self.description,
            "name": self.name,
            "paymentDate": _iso_z(self.payment_date),
            "status": self.status,
            "statusDate": _iso_z(self.status_date),
            "account": _json_load(self.account_json),
            "totalAmount": _json_load(self.total_amount_json),
            "paymentMethod": _json_load(self.payment_method_json),
            "channel": _json_load(self.channel_json),
            "paymentItem": _json_load(self.payment_item_json),
        }

        # drop nulls
        obj = {k: v for k, v in obj.items() if v is not None}

        # apply fields selection (top-level only)
        if fields_filter:
            allowed = set(f.strip() for f in fields_filter.split(",") if f.strip())
            allowed.update({"id", "href"})  # force for CTK
            obj = {k: v for k, v in obj.items() if k in allowed}

        return obj

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
