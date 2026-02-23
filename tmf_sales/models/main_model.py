from datetime import datetime, timezone
from odoo import api, fields, models


class TMFSalesLead(models.Model):
    _name = "tmf.sales.lead"
    _description = "TMF699 SalesLead"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(required=True)
    status = fields.Char(default="new")
    description = fields.Char()
    priority = fields.Char()
    expected_close_date = fields.Char(string="expectedCloseDate")
    creation_date_tmf = fields.Char(string="creationDate")
    status_change_date_tmf = fields.Char(string="statusChangeDate")
    related_party = fields.Json(default=list)
    category = fields.Json(default=dict)
    channel = fields.Json(default=dict)
    market_segment = fields.Json(default=dict)
    marketing_campaign = fields.Json(default=dict)
    sales_opportunity = fields.Json(default=dict)
    product = fields.Json(default=list)
    product_offering = fields.Json(default=list)
    product_specification = fields.Json(default=list)
    target_product_schema = fields.Json(default=dict)
    crm_lead_id = fields.Many2one("crm.lead", string="CRM Lead", index=True, ondelete="set null")
    extra_json = fields.Json(default=dict)

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _get_tmf_api_path(self):
        return "/sales/v4/salesLead"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "SalesLead",
            "name": self.name,
            "status": self.status or "new",
            "creationDate": self.creation_date_tmf or self._now_iso(),
            "statusChangeDate": self.status_change_date_tmf or self.creation_date_tmf or self._now_iso(),
        }
        if self.description:
            payload["description"] = self.description
        if self.priority:
            payload["priority"] = self.priority
        if self.expected_close_date:
            payload["expectedCloseDate"] = self.expected_close_date
        if self.related_party:
            payload["relatedParty"] = self.related_party
        if self.category:
            payload["category"] = self.category
        if self.channel:
            payload["channel"] = self.channel
        if self.market_segment:
            payload["marketSegment"] = self.market_segment
        if self.marketing_campaign:
            payload["marketingCampaign"] = self.marketing_campaign
        if self.sales_opportunity:
            payload["salesOpportunity"] = self.sales_opportunity
        if self.product:
            payload["product"] = self.product
        if self.product_offering:
            payload["productOffering"] = self.product_offering
        if self.product_specification:
            payload["productSpecification"] = self.product_specification
        if self.target_product_schema:
            payload["targetProductSchema"] = self.target_product_schema
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return payload

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="salesLead",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @staticmethod
    def _tmf_priority_to_crm(priority):
        value = str(priority or "").strip().lower()
        if value in {"3", "high", "urgent"}:
            return "3"
        if value in {"2", "medium"}:
            return "2"
        if value in {"1", "low"}:
            return "1"
        return "0"

    def _crm_vals(self):
        self.ensure_one()
        return {
            "name": self.name or "SalesLead",
            "description": self.description or False,
            "priority": self._tmf_priority_to_crm(self.priority),
        }

    def _sync_to_crm_lead(self):
        crm_model = self.env["crm.lead"].sudo().with_context(skip_tmf_bridge=True)
        for rec in self:
            vals = rec._crm_vals()
            if rec.crm_lead_id:
                rec.crm_lead_id.with_context(skip_tmf_bridge=True).write(vals)
                if not rec.crm_lead_id.tmf_sales_lead_id:
                    rec.crm_lead_id.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": rec.id})
            else:
                crm_lead = crm_model.create(vals)
                rec.with_context(skip_crm_sync=True).write({"crm_lead_id": crm_lead.id})
                crm_lead.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": rec.id})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            created = vals.get("creation_date_tmf") or self._now_iso()
            vals.setdefault("creation_date_tmf", created)
            vals.setdefault("status_change_date_tmf", vals.get("status_change_date_tmf") or created)
        recs = super().create(vals_list)
        if not self.env.context.get("skip_crm_sync"):
            recs._sync_to_crm_lead()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        vals = dict(vals)
        if "status" in vals and "status_change_date_tmf" not in vals:
            vals["status_change_date_tmf"] = self._now_iso()
        previous = {rec.id: rec.status for rec in self}
        res = super().write(vals)
        if not self.env.context.get("skip_crm_sync"):
            self._sync_to_crm_lead()
        for rec in self:
            self._notify("update", rec)
            if "status" in vals and previous.get(rec.id) != rec.status:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        if not self.env.context.get("skip_crm_sync"):
            for rec in self:
                if rec.crm_lead_id and rec.crm_lead_id.tmf_sales_lead_id.id == rec.id:
                    rec.crm_lead_id.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": False})
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="salesLead",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res
