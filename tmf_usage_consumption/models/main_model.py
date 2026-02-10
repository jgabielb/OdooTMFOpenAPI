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
    """
    TMF677: attribute selection via ?fields= applies to first-level attributes.
    We must always preserve 'href', 'id', and '@type' as these are critical identifiers.
    """
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

    # Store whole TMF payload (except id/href/@type which we manage)
    tmf_type = fields.Char(string="@type", default="QueryUsageConsumption", required=True)
    usage_consumption_json = fields.Text(string="usageConsumption(JSON)")  # list of objects
    party_account_json = fields.Text(string="partyAccount(JSON)")          # dict
    related_party_json = fields.Text(string="relatedParty(JSON)")          # dict
    search_criteria_json = fields.Text(string="searchCriteria(JSON)")      # dict
    error_message_json = fields.Text(string="errorMessage(JSON)")          # dict

    def _get_tmf_api_path(self):
        return f"{API_BASE}/queryUsageConsumption"

    def to_tmf_json(self, fields_filter=None):
        self.ensure_one()

        out = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "QueryUsageConsumption",
        }

        # 1. Handle usageConsumption as a list of UsageConsumptionReport items
        uc_val = _as_dict(self.usage_consumption_json)
        if uc_val is None:
            uc_val = []
        elif isinstance(uc_val, dict):
            uc_val = [uc_val]
        
        # Ensure items in the list have correct type and id/href
        out["usageConsumption"] = []
        for item in uc_val:
            if not isinstance(item, dict):
                continue
            # Ensure mandatory fields for the item
            if not item.get("id"):
                item["id"] = str(uuid.uuid4())
            if not item.get("@type"):
                item["@type"] = "UsageConsumptionReport"
            if not item.get("href"):
                item["href"] = f"{API_BASE}/usageConsumptionReport/{item['id']}"
            out["usageConsumption"].append(item)

        # 2. Handle searchCriteria
        sc = _as_dict(self.search_criteria_json)
        # Default searchCriteria points to a report with the same ID
        if sc is None:
            sc = {
                "id": self.tmf_id,
                "@type": "UsageConsumptionReport",
                "href": f"{API_BASE}/usageConsumptionReport/{self.tmf_id}"
            }
        else:
            if not sc.get("id"):
                sc["id"] = self.tmf_id
            if not sc.get("@type"):
                sc["@type"] = "UsageConsumptionReport"
            if not sc.get("href"):
                sc["href"] = f"{API_BASE}/usageConsumptionReport/{sc['id']}"
        
        out["searchCriteria"] = sc

        # 3. Optional fields
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

    def _get_tmf_api_path(self):
        return f"{API_BASE}/usageConsumptionReport"

    def to_tmf_json(self, fields_filter=None):
        self.ensure_one()
        out = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "UsageConsumptionReport",
        }
        
        # Handle bucket as a List of BucketRefOrValue
        b_val = _as_dict(self.bucket_json)
        if b_val is not None:
            # Spec expects a list. If we have a single dict, wrap it.
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