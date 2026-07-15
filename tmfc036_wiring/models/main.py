# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models


def _loads(v):
    if v in (None, False, ""):
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return None


def _as_list(v):
    v = _loads(v)
    if isinstance(v, dict):
        return [v]
    return v if isinstance(v, list) else []


def _collect(items):
    party, roles = [], []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("id") or "").strip()
        if not rid:
            continue
        if it.get("@type") in ("PartyRole", "PartyRoleRef"):
            roles.append(rid)
        else:
            party.append(rid)
    return party, roles


def _ref_ids(items):
    return [str(i.get("id")).strip() for i in (items or [])
            if isinstance(i, dict) and i.get("id")]


class TMFC036SalesLead(models.Model):
    _inherit = "tmf.sales.lead"

    tmfc036_related_partner_ids = fields.Many2many(
        "res.partner", "tmfc036_lead_partner_rel", "lead_id", "partner_id",
        string="TMFC036 Related Partners",
    )
    tmfc036_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmfc036_lead_party_role_rel", "lead_id", "party_role_id",
        string="TMFC036 Party Roles",
    )
    tmfc036_product_offering_ids = fields.Many2many(
        "product.template", "tmfc036_lead_offering_rel", "lead_id", "offering_id",
        string="TMFC036 Product Offerings (TMF620)",
    )
    tmfc036_product_specification_ids = fields.Many2many(
        "tmf.product.specification", "tmfc036_lead_product_spec_rel",
        "lead_id", "spec_id", string="TMFC036 Product Specifications (TMF620)",
    )
    tmfc036_quote_ids = fields.Many2many(
        "tmf.quote", "tmfc036_lead_quote_rel", "lead_id", "quote_id",
        string="TMFC036 Quotes (TMF648)",
    )
    tmfc036_agreement_ids = fields.Many2many(
        "tmf.agreement", "tmfc036_lead_agreement_rel", "lead_id", "agreement_id",
        string="TMFC036 Agreements (TMF651)",
    )
    tmfc036_agreement_spec_ids = fields.Many2many(
        "tmf.agreement.specification", "tmfc036_lead_agreement_spec_rel",
        "lead_id", "agreement_spec_id",
        string="TMFC036 Agreement Specifications (TMF651)",
    )
    tmfc036_product_order_ids = fields.Many2many(
        "sale.order", "tmfc036_lead_product_order_rel", "lead_id", "order_id",
        string="TMFC036 Product Orders (TMF622)",
    )

    _TMFC036_WIRING_KEYS = frozenset((
        "related_party", "product_offering", "product_specification",
        "product", "extra_json",
    ))

    def _tmfc036_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            def _rebuild(field_name, model, ids, id_field="tmf_id"):
                # rebuild-if-different: JSON refs are authoritative when present
                if not ids:
                    return
                found = self.env[model].sudo().search([(id_field, "in", ids)])
                if found and set(found.ids) != set(rec[field_name].ids):
                    updates[field_name] = [(6, 0, found.ids)]

            party_refs, role_refs = _collect(_as_list(rec.related_party))
            if party_refs:
                _rebuild("tmfc036_related_partner_ids", "res.partner", party_refs)
            if role_refs:
                _rebuild("tmfc036_party_role_ids", "tmf.party.role", role_refs)

            _rebuild("tmfc036_product_offering_ids", "product.template",
                     _ref_ids(_as_list(rec.product_offering)))
            _rebuild("tmfc036_product_specification_ids", "tmf.product.specification",
                     _ref_ids(_as_list(rec.product_specification)))

            extra = _loads(rec.extra_json) or {}
            _rebuild("tmfc036_quote_ids", "tmf.quote",
                     _ref_ids(_as_list(extra.get("quote"))))
            _rebuild("tmfc036_agreement_ids", "tmf.agreement",
                     _ref_ids(_as_list(extra.get("agreement"))))
            _rebuild("tmfc036_agreement_spec_ids", "tmf.agreement.specification",
                     _ref_ids(_as_list(extra.get("agreementSpecification"))))
            _rebuild("tmfc036_product_order_ids", "sale.order",
                     _ref_ids(_as_list(extra.get("productOrder"))))

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc036_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
                self._TMFC036_WIRING_KEYS & set(vals.keys())):
            try:
                self._tmfc036_resolve_refs()
            except Exception:
                pass
        return res


class TMFC036WiringTools(models.AbstractModel):
    _name = "tmfc036.wiring.tools"
    _description = "TMFC036 Wiring Tools"

    def _extract_id(self, payload):
        if not isinstance(payload, dict):
            return ""
        event = payload.get("event")
        if isinstance(event, dict):
            if isinstance(event.get("resource"), dict):
                return str(event["resource"].get("id") or "").strip()
            for v in event.values():
                if isinstance(v, dict) and v.get("id"):
                    return str(v["id"]).strip()
        if isinstance(payload.get("resource"), dict):
            return str(payload["resource"].get("id") or "").strip()
        return str(payload.get("id") or "").strip()

    def _refresh_leads(self, ref_id=None):
        Lead = self.env["tmf.sales.lead"].sudo()
        leads = Lead.search([])
        if ref_id:
            affected = leads.filtered(
                lambda l: ref_id in json.dumps({
                    "rp": l.related_party, "po": l.product_offering,
                    "ps": l.product_specification, "x": l.extra_json,
                }, default=str))
            leads = affected or leads
        leads._tmfc036_resolve_refs()
        return True

    @api.model
    def _handle_party_event(self, payload):
        return self._refresh_leads(self._extract_id(payload))

    @api.model
    def _handle_party_role_event(self, payload):
        return self._handle_party_event(payload)

    @api.model
    def _handle_product_catalog_event(self, payload):
        """TMF620 offering/spec/POP events: re-resolve leads referencing the id."""
        return self._refresh_leads(self._extract_id(payload))

    @api.model
    def _handle_product_order_event(self, payload):
        return self._refresh_leads(self._extract_id(payload))

    @api.model
    def _handle_agreement_event(self, payload):
        return self._refresh_leads(self._extract_id(payload))

    @api.model
    def _handle_quote_event(self, payload):
        return self._refresh_leads(self._extract_id(payload))
