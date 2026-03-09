# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TMFPartnershipSpecification(models.Model):
    _name = "tmf.partnership.specification"
    _description = "TMF668 PartnershipSpecification"
    _rec_name = "name"

    tmf_id = fields.Char(string="TMF id", index=True, required=True)
    href = fields.Char(string="href", index=True)
    name = fields.Char(required=True)
    description = fields.Text()
    role_specification_json = fields.Text(string="roleSpecification")  # list of objects as JSON string
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

    _sql_constraints = [
        ("tmf_id_unique", "unique(tmf_id)", "TMF id must be unique."),
    ]

    def _sync_product_link(self):
        env_pt = self.env["product.template"].sudo()
        for rec in self:
            pt = False
            if rec.tmf_id:
                pt = env_pt.search([("tmf_id", "=", rec.tmf_id)], limit=1)
            if not pt and rec.name:
                pt = env_pt.search([("name", "=", rec.name)], limit=1)
            if not pt and rec.name:
                pt = env_pt.create({"name": rec.name})
            if pt and rec.product_tmpl_id.id != pt.id:
                rec.with_context(skip_tmf_product_sync=True).write({"product_tmpl_id": pt.id})

    def _to_tmf_json(self):
        return {
            "id": self.tmf_id,
            "href": self.href or f"/tmf-api/partnershipManagement/v4/partnershipSpecification/{self.tmf_id}",
            "name": self.name,
            "description": self.description,
            "@type": "PartnershipSpecification",
        }

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PartnershipSpecificationCreateEvent",
            "update": "PartnershipSpecificationAttributeValueChangeEvent",
            "delete": "PartnershipSpecificationDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec._to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("partnershipSpecification", event_name, payload)
            except Exception:
                continue

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_product_link()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_tmf_product_sync"):
            return res
        if "name" in vals or "tmf_id" in vals:
            self._sync_product_link()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec._to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
