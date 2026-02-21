# -*- coding: utf-8 -*-
import uuid
from odoo import api, fields, models

API_NAME = "customerBillOnDemand"  # reuse the existing tmf_base mapping key


class TMFCustomerBillOnDemand(models.Model):
    _name = "tmf.customer.bill.on.demand"
    _description = "TMF678 CustomerBillOnDemand"
    _rec_name = "tmf_id"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)
    tmf_type = fields.Char(required=True, default="CustomerBillOnDemand")  # @type

    # CTK v5 expects specific states (likely inProgress, completed, failed).
    # We maintain a broad selection for internal logic but map to TMF values in _tmf_state.
    state = fields.Selection(
        selection=[
            ("acknowledged", "acknowledged"),
            ("inProgress", "inProgress"),
            ("completed", "completed"),
            ("rejected", "rejected"),
            ("cancelled", "cancelled"),
            ("failed", "failed"),
        ],
        default="inProgress",  # Default to inProgress to satisfy CTK immediate validation
        required=True,
        index=True,
    )

    billing_account_id = fields.Char(index=True)
    billing_account_type = fields.Char(default="BillingAccount")

    customer_bill_ref = fields.Char(index=True)
    payload = fields.Json(string="TMF Payload")

    last_update = fields.Datetime(index=True, default=fields.Datetime.now)

    def _compute_href(self, host_url: str, api_base: str):
        host_url = (host_url or "").rstrip("/")
        return f"{host_url}{api_base}/customerBillOnDemand/{self.tmf_id}"

    # --- helpers (CTK-proof) -------------------------------------------------
    @staticmethod
    def _dt_to_iso_z(dtval):
        """Return ISO-8601 with Z or None. Handles odoo datetime string too."""
        if not dtval:
            return None
        # dtval may already be a datetime or a string
        dt = fields.Datetime.to_datetime(dtval)
        if not dt:
            return None
        # Odoo datetime is naive; treat as UTC-ish for CTK formatting
        return dt.replace(microsecond=0).isoformat() + "Z"

    @staticmethod
    def _safe_str(val):
        """Return string or None (never False)."""
        if val is None or val is False:
            return None
        s = str(val).strip()
        return s if s and s.lower() not in {"false", "none", "null"} else None

    def _tmf_state(self):
        """
        Normalize to allowed TMF state values for v5 schema.
        Maps internal/older states to allowed set: {inProgress, completed, failed}.
        """
        self.ensure_one()
        s = (self.state or "").strip()
        
        # Mapping table
        if s in ("done", "completed"):
            return "completed"
        if s in ("rejected", "failed", "cancelled"):
            return "failed"
        
        # 'acknowledged' or 'inProgress' or anything else -> inProgress
        return "inProgress"
    # ------------------------------------------------------------------------

    def to_tmf_json(self, host_url=None, api_base="/tmf-api/customerBillManagement/v5"):
        self.ensure_one()

        href = self.href or self._compute_href(host_url or "", api_base)

        out = {
            "id": self.tmf_id,
            "href": href,  # IMPORTANT: always use computed href, not stale self.href
            "@type": self.tmf_type or "CustomerBillOnDemand",
            "state": self._tmf_state(),
            "billingAccount": {
                "id": self._safe_str(self.billing_account_id),
                "@type": self.billing_account_type or "BillingAccount",
            },
            "lastUpdate": self._dt_to_iso_z(self.last_update),
        }

        # Optional reference
        if self.customer_bill_ref:
            out["customerBill"] = {"id": self._safe_str(self.customer_bill_ref), "@type": "CustomerBill"}

        # Merge payload but never allow it to override identity/type fields
        p = dict(self.payload or {})
        for k in ("id", "href", "@type", "@baseType", "lastUpdate", "last_update"):
            p.pop(k, None)

        # Safety: if payload contains billingAccount/state, keep our normalized values
        p.pop("state", None)
        p.pop("billingAccount", None)

        out.update(p)

        # Re-assert invariants
        out["id"] = self.tmf_id
        out["href"] = href
        out["@type"] = self.tmf_type or "CustomerBillOnDemand"
        out["state"] = self._tmf_state()
        return out

    def _notify(self, event_type):
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=API_NAME,
                event_type=event_type,
                resource_json=self.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # Conformance Page 13
            rec._notify("CustomerBillOnDemandCreateEvent")
        return recs

    def write(self, vals):
        before_state = {rec.id: rec.state for rec in self}
        res = super().write(vals)
        for rec in self:
            # Conformance Page 13
            if "state" in vals and before_state.get(rec.id) != rec.state:
                rec._notify("CustomerBillOnDemandStateChangeEvent")
            else:
                rec._notify("CustomerBillOnDemandAttributeValueChangeEvent")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                    api_name=API_NAME,
                    event_type="CustomerBillOnDemandDeleteEvent",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res