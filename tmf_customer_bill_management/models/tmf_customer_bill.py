# -*- coding: utf-8 -*-
import uuid
from odoo import api, fields, models

API_NAME = "customerBill"  # must match TMF_EVENT_NAME_MAP key in tmf_base

class TMFCustomerBill(models.Model):
    _name = "tmf.customer.bill"
    _description = "TMF678 CustomerBill"
    _rec_name = "name"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)
    tmf_type = fields.Char(required=True, default="CustomerBill")  # @type

    name = fields.Char(index=True)
    state = fields.Char(index=True)
    bill_date = fields.Datetime(index=True)

    bill_cycle_id = fields.Many2one("tmf.bill.cycle", string="BillCycle")
    billing_period_start = fields.Datetime(index=True)
    billing_period_end = fields.Datetime(index=True)

    payload = fields.Json(string="TMF Payload")
    last_update = fields.Datetime(index=True, default=fields.Datetime.now)

    def _compute_href(self, host_url: str, api_base: str):
        host_url = (host_url or "").rstrip("/")
        return f"{host_url}{api_base}/customerBill/{self.tmf_id}"

    # -----------------------------
    # TMF JSON (minimal, CTK-safe)
    # -----------------------------
    def to_tmf_json(self):
        self.ensure_one()
        out = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type or "CustomerBill",
            "name": self.name,
            "state": self.state,
            "billDate": fields.Datetime.to_string(self.bill_date).replace(" ", "T") + "Z" if self.bill_date else None,
            "billingPeriod": {
                "startDateTime": fields.Datetime.to_string(self.billing_period_start).replace(" ", "T") + "Z" if self.billing_period_start else None,
                "endDateTime": fields.Datetime.to_string(self.billing_period_end).replace(" ", "T") + "Z" if self.billing_period_end else None,
            },
            "lastUpdate": fields.Datetime.to_string(self.last_update).replace(" ", "T") + "Z" if self.last_update else None,
        }

        if self.bill_cycle_id:
            out["billCycle"] = {
                "id": self.bill_cycle_id.tmf_id,
                "href": self.bill_cycle_id.href,
                "@type": self.bill_cycle_id.tmf_type or "BillCycle",
                "@referredType": "BillCycle",
            }

        # Merge stored payload
        p = dict(self.payload or {})
        p.pop("id", None); p.pop("href", None); p.pop("@type", None)
        out.update(p)

        # Conformance Page 8: billDocument is Mandatory (Array)
        if "billDocument" not in out or out["billDocument"] is None:
            out["billDocument"] = []

        out["id"] = self.tmf_id
        out["href"] = self.href
        out["@type"] = self.tmf_type or "CustomerBill"
        return out

    # -----------------------------
    # HUB NOTIFICATION (tmf_base)
    # -----------------------------
    def _notify(self, event_type):
        """
        event_type can be specific TMF strings found in Page 13 of Conformance Profile:
          - CustomerBillCreateEvent
          - CustomerBillStateChangeEvent
        """
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=API_NAME,
                event_type=event_type,
                resource_json=self.to_tmf_json(),
            )
        except Exception:
            # keep CTK-safe: never break CRUD if hub fails
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # Conformance Page 13: Mandatory Notification
            rec._notify("CustomerBillCreateEvent")
        return recs

    def write(self, vals):
        # detect state change on write
        before = {rec.id: rec.state for rec in self}
        res = super().write(vals)
        for rec in self:
            # Generic update not strictly mandatory in Page 13 list, but good practice.
            # However, StateChangeEvent IS mandatory.
            if "state" in vals and before.get(rec.id) != rec.state:
                rec._notify("CustomerBillStateChangeEvent")
            else:
                # Optional: AttributeValueChangeEvent
                rec._notify("CustomerBillAttributeValueChangeEvent")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                    api_name=API_NAME,
                    event_type="CustomerBillDeleteEvent", # Not strictly mandatory in v5 profile, but standard
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

    def apply_patch(self, patch: dict):
        """
        Conformance Page 19: Only 'billCycle' and 'state' are patchable.
        """
        allowed = {"billCycle", "state"}
        extra = set(patch.keys()) - allowed
        if extra:
            raise ValueError(f"Non-patchable attributes present: {sorted(extra)}")

        prev_state = self.state

        if "state" in patch:
            self.state = patch.get("state")

        if "billCycle" in patch:
            bc = patch.get("billCycle") or {}
            bc_id = bc.get("id")
            if bc_id:
                bill_cycle = self.env["tmf.bill.cycle"].sudo().search([("tmf_id", "=", bc_id)], limit=1)
                if bill_cycle:
                    self.bill_cycle_id = bill_cycle.id

        base = dict(self.payload or {})
        base.update({k: patch[k] for k in patch})
        self.payload = base
        self.last_update = fields.Datetime.now()

        # IMPORTANT: notify state-change here too (covers PATCH use-case)
        if "state" in patch and prev_state != self.state:
            self._notify("CustomerBillStateChangeEvent")
        else:
            self._notify("CustomerBillAttributeValueChangeEvent")