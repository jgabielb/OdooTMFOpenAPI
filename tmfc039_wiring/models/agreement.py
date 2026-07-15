# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models


def _loads(value):
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


class TMFC039Agreement(models.Model):
    _inherit = "tmf.agreement"

    tmfc039_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc039_agreement_partner_rel",
        column1="agreement_id",
        column2="partner_id",
        string="TMFC039 Engaged Parties",
    )
    tmfc039_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc039_agreement_party_role_rel",
        column1="agreement_id",
        column2="party_role_id",
        string="TMFC039 Party Roles",
    )
    tmfc039_product_specification_ids = fields.Many2many(
        comodel_name="tmf.product.specification",
        relation="tmfc039_agreement_product_spec_rel",
        column1="agreement_id",
        column2="product_spec_id",
        string="TMFC039 Product Specifications",
    )
    tmfc039_product_offering_ids = fields.Many2many(
        comodel_name="product.template",
        relation="tmfc039_agreement_offering_rel",
        column1="agreement_id",
        column2="offering_id",
        string="TMFC039 Product Offerings (TMF620)",
    )
    tmfc039_product_ids = fields.Many2many(
        comodel_name="tmf.product",
        relation="tmfc039_agreement_product_rel",
        column1="agreement_id",
        column2="product_id",
        string="TMFC039 Products (TMF637)",
    )
    tmfc039_document_ids = fields.Many2many(
        comodel_name="tmf.document",
        relation="tmfc039_agreement_document_rel",
        column1="agreement_id",
        column2="document_id",
        string="TMFC039 Documents (TMF667)",
    )

    def _tmfc039_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        PSpec = self.env["tmf.product.specification"].sudo()
        for rec in self:
            updates = {}
            engaged = _loads(rec.engaged_party) or []
            if isinstance(engaged, dict):
                engaged = [engaged]
            party_refs, role_refs = [], []
            for it in engaged:
                if not isinstance(it, dict):
                    continue
                ref_id = str(it.get("id") or "").strip()
                if not ref_id:
                    continue
                if it.get("@type") in ("PartyRole", "PartyRoleRef"):
                    role_refs.append(ref_id)
                else:
                    party_refs.append(ref_id)
            if party_refs:
                partners = Partner.search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc039_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc039_party_role_ids"] = [(6, 0, roles.ids)]

            items = _loads(rec.agreement_item) or []
            if isinstance(items, dict):
                items = [items]
            spec_refs, offering_refs, product_refs = [], [], []
            for it in items:
                if not isinstance(it, dict):
                    continue
                po = it.get("productOffering")
                po_list = [po] if isinstance(po, dict) else (po if isinstance(po, list) else [])
                for ref in po_list:
                    if isinstance(ref, dict) and ref.get("id"):
                        offering_refs.append(str(ref["id"]))
                ps = it.get("productSpecification")
                ps_list = [ps] if isinstance(ps, dict) else (ps if isinstance(ps, list) else [])
                for ref in ps_list:
                    if isinstance(ref, dict) and ref.get("id"):
                        spec_refs.append(str(ref["id"]))
                prod = it.get("product")
                if isinstance(prod, dict):
                    if prod.get("id"):
                        product_refs.append(str(prod["id"]))
                    ps2 = prod.get("productSpecification")
                    if isinstance(ps2, dict) and ps2.get("id"):
                        spec_refs.append(str(ps2["id"]))
            if spec_refs:
                specs = PSpec.search([("tmf_id", "in", spec_refs)])
                if specs:
                    updates["tmfc039_product_specification_ids"] = [(6, 0, specs.ids)]
            if offering_refs:
                offerings = self.env["product.template"].sudo().search(
                    [("tmf_id", "in", offering_refs)])
                if offerings:
                    updates["tmfc039_product_offering_ids"] = [(6, 0, offerings.ids)]
            if product_refs:
                products = self.env["tmf.product"].sudo().search(
                    [("tmf_id", "in", product_refs)])
                if products:
                    updates["tmfc039_product_ids"] = [(6, 0, products.ids)]

            # TMF667 documents referenced from agreement attachments/documents
            doc_refs = []
            for attr in ("attachment", "document", "associated_agreement"):
                if attr in rec._fields:
                    values = _loads(rec[attr]) or []
                    if isinstance(values, dict):
                        values = [values]
                    for ref in values:
                        if (isinstance(ref, dict) and ref.get("id")
                                and (ref.get("@referredType") or ref.get("@type"))
                                in ("Document", "DocumentRef", "AttachmentRef")):
                            doc_refs.append(str(ref["id"]))
            if doc_refs:
                docs = self.env["tmf.document"].sudo().search(
                    [("tmf_id", "in", doc_refs)])
                if docs:
                    updates["tmfc039_document_ids"] = [(6, 0, docs.ids)]

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc039_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "engaged_party" in vals or "agreement_item" in vals
        ):
            try:
                self._tmfc039_resolve_refs()
            except Exception:
                pass
        return res
