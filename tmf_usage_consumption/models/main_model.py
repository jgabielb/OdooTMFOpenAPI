# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import uuid
from datetime import datetime

API_BASE = "/tmf-api/usageConsumptionManagement/v5"

def _now_z():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _as_dict(val):
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None
    return None

def _filter_top_level_fields(payload, fields_filter):
    if not fields_filter:
        return payload
    allowed = set([f.strip() for f in fields_filter.split(",") if f.strip()])
    allowed.add("href")
    allowed.add("id")
    allowed.add("@type")
    return {k: v for k, v in payload.items() if k in allowed}


class TMFQueryUsageConsumption(models.Model):
    _name = "tmf.query.usage.consumption"
    _description = "QueryUsageConsumption"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", default="QueryUsageConsumption", required=True)
    usage_consumption_json = fields.Text(string="usageConsumption(JSON)")
    party_account_json = fields.Text(string="partyAccount(JSON)")
    related_party_json = fields.Text(string="relatedParty(JSON)")
    search_criteria_json = fields.Text(string="searchCriteria(JSON)")
    error_message_json = fields.Text(string="errorMessage(JSON)")

    # -----------------------------
    # HUB NOTIFICATION (TMF)
    # -----------------------------
    def _notify(self, action):
        # action MUST be: create | update | delete (matches your TMF_EVENT_NAME_MAP keys)
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name="queryUsageConsumption",
                event_type=action,
                resource_json=self.to_tmf_json(),
            )
        except Exception:
            # keep CTK-safe: do not break CRUD if hub fails
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._notify("update")
        return res

    def unlink(self):
        # capture payloads before delete
        payloads = [(rec, rec.to_tmf_json()) for rec in self]
        res = super().unlink()
        for rec, payload in payloads:
            try:
                self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                    api_name="queryUsageConsumption",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

    # -----------------------------
    # TMF JSON
    # -----------------------------
    def _get_tmf_api_path(self):
        return f"{API_BASE}/queryUsageConsumption"

    def to_tmf_json(self, fields_filter=None):
        self.ensure_one()

        out = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "QueryUsageConsumption",
        }

        uc_val = _as_dict(self.usage_consumption_json)
        if uc_val is None:
            uc_val = []
        elif isinstance(uc_val, dict):
            uc_val = [uc_val]

        out["usageConsumption"] = []
        for item in uc_val:
            if not isinstance(item, dict):
                continue
            if not item.get("id"):
                item["id"] = str(uuid.uuid4())
            if not item.get("@type"):
                item["@type"] = "UsageConsumptionReport"
            if not item.get("href"):
                item["href"] = f"{API_BASE}/usageConsumptionReport/{item['id']}"
            out["usageConsumption"].append(item)

        sc = _as_dict(self.search_criteria_json)
        if sc is None:
            sc = {
                "id": self.tmf_id,
                "@type": "UsageConsumptionReport",
                "href": f"{API_BASE}/usageConsumptionReport/{self.tmf_id}",
            }
        else:
            if not sc.get("id"):
                sc["id"] = self.tmf_id
            if not sc.get("@type"):
                sc["@type"] = "UsageConsumptionReport"
            if not sc.get("href"):
                sc["href"] = f"{API_BASE}/usageConsumptionReport/{sc['id']}"

        out["searchCriteria"] = sc

        pa = _as_dict(self.party_account_json)
        rp = _as_dict(self.related_party_json)
        em = _as_dict(self.error_message_json)

        if pa is not None:
            out["partyAccount"] = pa
        if rp is not None:
            out["relatedParty"] = rp
        if em is not None:
            out["errorMessage"] = em

        return _filter_top_level_fields(out, fields_filter)


class TMFUsageConsumptionReport(models.Model):
    _name = "tmf.usage.consumption.report"
    _description = "UsageConsumptionReport"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", default="UsageConsumptionReport", required=True)
    bucket_json = fields.Text(string="bucket(JSON)")

    # -----------------------------
    # HUB NOTIFICATION (TMF)
    # -----------------------------
    def _notify(self, action):
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name="usageConsumptionReport",
                event_type=action,
                resource_json=self.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._notify("update")
        return res

    def unlink(self):
        payloads = [(rec, rec.to_tmf_json()) for rec in self]
        res = super().unlink()
        for rec, payload in payloads:
            try:
                self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                    api_name="usageConsumptionReport",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

    # -----------------------------
    # TMF JSON
    # -----------------------------
    def _get_tmf_api_path(self):
        return f"{API_BASE}/usageConsumptionReport"

    def to_tmf_json(self, fields_filter=None):
        self.ensure_one()
        out = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "UsageConsumptionReport",
        }

        b_val = _as_dict(self.bucket_json)
        if b_val is not None:
            if isinstance(b_val, dict):
                b_val = [b_val]

            if isinstance(b_val, list):
                valid_buckets = []
                for b in b_val:
                    if not isinstance(b, dict):
                        continue
                    if not b.get("id"):
                        b["id"] = str(uuid.uuid4())
                    if not b.get("@type"):
                        b["@type"] = "Bucket"
                    if not b.get("href"):
                        b["href"] = f"{API_BASE}/bucket/{b['id']}"
                    valid_buckets.append(b)
                out["bucket"] = valid_buckets

        return _filter_top_level_fields(out, fields_filter)
