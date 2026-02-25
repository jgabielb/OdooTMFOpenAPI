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
    move_id = fields.Many2one("account.move", string="Invoice", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    billing_period_start = fields.Datetime(index=True)
    billing_period_end = fields.Datetime(index=True)

    payload = fields.Json(string="TMF Payload")
    last_update = fields.Datetime(index=True, default=fields.Datetime.now)

    def _sync_account_move(self):
        Move = self.env["account.move"].sudo()
        for rec in self:
            if not rec.partner_id:
                continue
            move_vals = {
                "move_type": "out_invoice",
                "partner_id": rec.partner_id.id,
                "invoice_date": fields.Date.to_date(rec.bill_date) if rec.bill_date else False,
                "ref": rec.tmf_id,
                "invoice_origin": rec.name or rec.tmf_id,
            }
            if rec.move_id and rec.move_id.exists():
                # Keep this conservative: update only while draft.
                if rec.move_id.state == "draft":
                    rec.move_id.write(move_vals)
            else:
                rec.move_id = Move.create(move_vals).id

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

        if self.move_id:
            out.setdefault("relatedEntity", [])
            out["relatedEntity"].append({
                "id": str(self.move_id.id),
                "name": self.move_id.name,
                "@referredType": "Invoice",
            })
        if self.partner_id:
            out.setdefault("billingAccount", {
                "id": str(self.partner_id.tmf_id or self.partner_id.id),
                "name": self.partner_id.name,
                "@referredType": "Customer",
            })

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
        for vals in vals_list:
            move_id = vals.get("move_id")
            payload = vals.get("payload") or {}
            if not move_id and isinstance(payload, dict):
                related_entities = payload.get("relatedEntity") or []
                for ent in related_entities:
                    if not isinstance(ent, dict):
                        continue
                    rid = ent.get("id")
                    if not rid:
                        continue
                    move = self.env["account.move"].sudo().search([("tmf_id", "=", str(rid))], limit=1)
                    if not move and str(rid).isdigit():
                        move = self.env["account.move"].sudo().browse(int(rid))
                    if move and move.exists():
                        move_id = move.id
                        vals["move_id"] = move.id
                        break
            if move_id and not vals.get("partner_id"):
                move = self.env["account.move"].sudo().browse(move_id)
                if move and move.exists() and move.partner_id:
                    vals["partner_id"] = move.partner_id.id
        recs = super().create(vals_list)
        recs._sync_account_move()
        for rec in recs:
            # Conformance Page 13: Mandatory Notification
            rec._notify("CustomerBillCreateEvent")
        return recs

    def write(self, vals):
        # detect state change on write
        before = {rec.id: rec.state for rec in self}
        res = super().write(vals)
        self._sync_account_move()
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
