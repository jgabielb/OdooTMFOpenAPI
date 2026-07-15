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


class TMFC009ServiceQualification(models.Model):
    _inherit = "tmf.service.qualification"

    tmfc009_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc009_sq_partner_rel",
        column1="sq_id",
        column2="partner_id",
        string="TMFC009 Related Partners",
    )
    tmfc009_party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc009_sq_party_role_rel",
        column1="sq_id",
        column2="party_role_id",
        string="TMFC009 Party Roles",
    )
    tmfc009_service_specification_ids = fields.Many2many(
        comodel_name="tmf.service.specification",
        relation="tmfc009_sq_service_spec_rel",
        column1="sq_id",
        column2="service_spec_id",
        string="TMFC009 Service Specifications",
    )
    tmfc009_service_ids = fields.Many2many(
        comodel_name="tmf.service",
        relation="tmfc009_sq_service_rel",
        column1="sq_id",
        column2="service_id",
        string="TMFC009 Services (TMF638)",
    )
    tmfc009_resource_ids = fields.Many2many(
        comodel_name="stock.lot",
        relation="tmfc009_sq_resource_rel",
        column1="sq_id",
        column2="resource_id",
        string="TMFC009 Resources (TMF639)",
    )
    tmfc009_resource_specification_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        relation="tmfc009_sq_resource_spec_rel",
        column1="sq_id",
        column2="resource_spec_id",
        string="TMFC009 Resource Specifications (TMF634)",
    )
    tmfc009_geographic_address_id = fields.Many2one(
        "tmf.geographic.address", string="Geographic Address (TMF673)",
        index=True, ondelete="set null")
    tmfc009_geographic_site_id = fields.Many2one(
        "tmf.geographic.site", string="Geographic Site (TMF674)",
        index=True, ondelete="set null")
    tmfc009_geographic_location_id = fields.Many2one(
        "tmf.geographic.location", string="Geographic Location (TMF675)",
        index=True, ondelete="set null")

    def _tmfc009_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        PartyRole = self.env["tmf.party.role"].sudo()
        ServiceSpec = self.env["tmf.service.specification"].sudo()
        for rec in self:
            updates = {}
            parties = _loads(rec.related_party_json) or []
            party_refs, role_refs = [], []
            for it in parties:
                if not isinstance(it, dict):
                    continue
                rid = str(it.get("id") or "").strip()
                if not rid:
                    continue
                if it.get("@type") in ("PartyRole", "PartyRoleRef"):
                    role_refs.append(rid)
                else:
                    party_refs.append(rid)
            if party_refs:
                partners = Partner.search([("tmf_id", "in", party_refs)])
                if partners:
                    updates["tmfc009_related_partner_ids"] = [(6, 0, partners.ids)]
            if role_refs:
                roles = PartyRole.search([("tmf_id", "in", role_refs)])
                if roles:
                    updates["tmfc009_party_role_ids"] = [(6, 0, roles.ids)]

            spec_refs, service_refs, resource_refs, resource_spec_refs = [], [], [], []
            place_refs = []
            items = _loads(rec.service_qualification_item_json) or []
            for it in items:
                if not isinstance(it, dict):
                    continue
                svc = it.get("service") or {}
                if not isinstance(svc, dict):
                    continue
                sid = str(svc.get("id") or "").strip()
                if sid:
                    service_refs.append(sid)
                spec = svc.get("serviceSpecification")
                if isinstance(spec, dict):
                    spec_id = str(spec.get("id") or "").strip()
                    if spec_id:
                        spec_refs.append(spec_id)
                supporting = svc.get("supportingResource") or []
                if isinstance(supporting, dict):
                    supporting = [supporting]
                for res in supporting:
                    if not isinstance(res, dict):
                        continue
                    rid = str(res.get("id") or "").strip()
                    if rid:
                        resource_refs.append(rid)
                    res_spec = res.get("resourceSpecification")
                    if isinstance(res_spec, dict) and res_spec.get("id"):
                        resource_spec_refs.append(str(res_spec["id"]).strip())
                places = svc.get("place") or []
                if isinstance(places, dict):
                    places = [places]
                place_refs.extend(p for p in places if isinstance(p, dict))

            if spec_refs:
                specs = ServiceSpec.search([("tmf_id", "in", spec_refs)])
                if specs:
                    updates["tmfc009_service_specification_ids"] = [(6, 0, specs.ids)]
            if service_refs:
                services = self.env["tmf.service"].sudo().search(
                    [("tmf_id", "in", service_refs)])
                if services:
                    updates["tmfc009_service_ids"] = [(6, 0, services.ids)]
            if resource_refs:
                resources = self.env["stock.lot"].sudo().search(
                    [("tmf_id", "in", resource_refs)])
                if resources:
                    updates["tmfc009_resource_ids"] = [(6, 0, resources.ids)]
            if resource_spec_refs:
                res_specs = self.env["tmf.resource.specification"].sudo().search(
                    [("tmf_id", "in", resource_spec_refs)])
                if res_specs:
                    updates["tmfc009_resource_specification_ids"] = [(6, 0, res_specs.ids)]

            geo_map = {
                ("GeographicAddress", "GeographicAddressRef"):
                    ("tmfc009_geographic_address_id", "tmf.geographic.address"),
                ("GeographicSite", "GeographicSiteRef"):
                    ("tmfc009_geographic_site_id", "tmf.geographic.site"),
                ("GeographicLocation", "GeographicLocationRef"):
                    ("tmfc009_geographic_location_id", "tmf.geographic.location"),
            }
            for types, (geo_field, geo_model) in geo_map.items():
                geo_ids = [str(p.get("id") or "").strip() for p in place_refs
                           if p.get("@type") in types and p.get("id")]
                if not geo_ids:
                    continue
                match = self.env[geo_model].sudo().search(
                    [("tmf_id", "in", geo_ids)], limit=1)
                if match and rec[geo_field].id != match.id:
                    updates[geo_field] = match.id

            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc009_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "related_party_json" in vals or "service_qualification_item_json" in vals
        ):
            try:
                self._tmfc009_resolve_refs()
            except Exception:
                pass
        return res
