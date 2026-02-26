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
    partner_id = fields.Many2one("res.partner", string="Partner", index=True, ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Sales Order", index=True, ondelete="set null")
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
        elif self.sale_order_id:
            payload["salesOpportunity"] = {
                "id": self.sale_order_id.name or str(self.sale_order_id.id),
                "@type": "SalesOpportunityRef",
            }
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
        vals = {
            "name": self.name or "SalesLead",
            "description": self.description or False,
            "priority": self._tmf_priority_to_crm(self.priority),
        }
        if self.partner_id:
            vals["partner_id"] = self.partner_id.id
        return vals

    def _resolve_partner_from_tmf(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        entries = self.related_party if isinstance(self.related_party, list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pid = str(entry.get("id") or "").strip()
            pname = str(entry.get("name") or "").strip()
            if pid and "tmf_id" in Partner._fields:
                partner = Partner.search([("tmf_id", "=", pid)], limit=1)
                if partner:
                    return partner
            if pid.isdigit():
                partner = Partner.browse(int(pid))
                if partner.exists():
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
                create_vals = {"name": pname}
                if pid and "tmf_id" in Partner._fields:
                    create_vals["tmf_id"] = pid
                return Partner.create(create_vals)
        return Partner

    def _sync_to_crm_lead(self):
        crm_model = self.env["crm.lead"].sudo().with_context(skip_tmf_bridge=True)
        for rec in self:
            partner = rec.partner_id or rec._resolve_partner_from_tmf()
            if partner and rec.partner_id != partner:
                rec.with_context(skip_crm_sync=True, skip_sale_sync=True).write({"partner_id": partner.id})
            vals = rec._crm_vals()
            if rec.crm_lead_id:
                rec.crm_lead_id.with_context(skip_tmf_bridge=True).write(vals)
                if not rec.crm_lead_id.tmf_sales_lead_id:
                    rec.crm_lead_id.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": rec.id})
            else:
                crm_lead = crm_model.create(vals)
                rec.with_context(skip_crm_sync=True).write({"crm_lead_id": crm_lead.id})
                crm_lead.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": rec.id})

    def _sync_to_sale_order(self):
        SaleOrder = self.env["sale.order"].sudo().with_context(skip_tmf_bridge=True)
        for rec in self:
            partner = rec.partner_id
            if not partner:
                continue
            order = rec.sale_order_id
            if not order:
                opportunity = rec.sales_opportunity if isinstance(rec.sales_opportunity, dict) else {}
                opp_id = str(opportunity.get("id") or "").strip()
                if opp_id:
                    if opp_id.isdigit():
                        candidate = SaleOrder.browse(int(opp_id))
                        if candidate.exists():
                            order = candidate
                    if not order:
                        order = SaleOrder.search(
                            ["|", ("name", "=", opp_id), ("client_order_ref", "=", opp_id)],
                            limit=1,
                            order="id desc",
                        )
            vals = {
                "partner_id": partner.id,
                "client_order_ref": rec.tmf_id,
                "origin": rec.name or rec.tmf_id,
            }
            if rec.crm_lead_id and "opportunity_id" in SaleOrder._fields:
                vals["opportunity_id"] = rec.crm_lead_id.id
            if order:
                order.write(vals)
            else:
                order = SaleOrder.create(vals)
            if order and rec.sale_order_id != order:
                rec.with_context(skip_sale_sync=True, skip_crm_sync=True).write({"sale_order_id": order.id})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            created = vals.get("creation_date_tmf") or self._now_iso()
            vals.setdefault("creation_date_tmf", created)
            vals.setdefault("status_change_date_tmf", vals.get("status_change_date_tmf") or created)
        recs = super().create(vals_list)
        if not self.env.context.get("skip_crm_sync"):
            recs._sync_to_crm_lead()
        if not self.env.context.get("skip_sale_sync"):
            recs._sync_to_sale_order()
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
        if not self.env.context.get("skip_sale_sync"):
            self._sync_to_sale_order()
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
                if rec.sale_order_id and "tmf_sales_lead_id" in rec.sale_order_id._fields:
                    rec.sale_order_id.with_context(skip_tmf_bridge=True).write({"tmf_sales_lead_id": False})
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
