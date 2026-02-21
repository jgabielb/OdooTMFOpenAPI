# -*- coding: utf-8 -*-
import uuid
from odoo import api, fields, models


class TMFBillCycle(models.Model):
    _name = "tmf.bill.cycle"
    _description = "TMF678 BillCycle"
    _rec_name = "name"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)
    tmf_type = fields.Char(required=True, default="BillCycle")  # @type

    name = fields.Char()
    # billingDate is Mandatory (Page 7). Added default to help new records.
    billing_date = fields.Datetime(default=fields.Datetime.now)
    payload = fields.Json(string="TMF Payload")

    last_update = fields.Datetime(index=True, default=fields.Datetime.now)

    def _compute_href(self, host_url: str, api_base: str):
        host_url = (host_url or "").rstrip("/")
        return f"{host_url}{api_base}/billCycle/{self.tmf_id}"

    @staticmethod
    def _dt_to_iso_z(dtval):
        if not dtval:
            return None
        dt = fields.Datetime.to_datetime(dtval)
        if not dt:
            return None
        return dt.replace(microsecond=0).isoformat() + "Z"

    def to_tmf_json(self, host_url=None, api_base="/tmf-api/customerBillManagement/v5"):
        self.ensure_one()
        href = self.href or self._compute_href(host_url or "", api_base)

        # MANDATORY: billingDate must be present and string.
        # Fallback to create_date or last_update (STABLE) instead of now() to avoid CTK drift errors.
        b_date = self._dt_to_iso_z(self.billing_date)
        if not b_date:
            fallback = self.create_date or self.last_update or fields.Datetime.now()
            b_date = self._dt_to_iso_z(fallback)

        out = {
            "id": self.tmf_id,
            "href": href,
            "@type": self.tmf_type or "BillCycle",
            "name": self.name or None,
            "billingDate": b_date,
            "lastUpdate": self._dt_to_iso_z(self.last_update),
        }

        # Merge payload but never override identity/type fields
        p = dict(self.payload or {})
        for k in ("id", "href", "@type", "@baseType", "billingDate", "lastUpdate", "billing_date", "last_update"):
            p.pop(k, None)

        out.update(p)
        
        # Conformance Page 7: BillCycleSpecification is Mandatory.
        out["id"] = self.tmf_id
        out["href"] = href
        out["@type"] = self.tmf_type or "BillCycle"
        return out


class TMFBillCycleSpecification(models.Model):
    _name = "tmf.bill.cycle.spec"
    _description = "TMF BillCycleSpecification"
    _rec_name = "name"

    tmf_id = fields.Char(index=True, required=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(index=True)
    tmf_type = fields.Char(required=True, default="BillCycleSpecification")
    name = fields.Char()
    payload = fields.Json(string="TMF Payload")