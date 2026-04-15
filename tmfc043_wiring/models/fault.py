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


def _extract_ids(blob):
    out = []
    if not blob:
        return out
    if isinstance(blob, dict):
        blob = [blob]
    if not isinstance(blob, list):
        return out
    for it in blob:
        if isinstance(it, dict) and it.get("id"):
            out.append(str(it["id"]))
    return out


class TMFC043TroubleTicket(models.Model):
    _inherit = "tmf.trouble.ticket"

    tmfc043_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc043_tt_partner_rel",
        column1="ticket_id",
        column2="partner_id",
        string="TMFC043 Engaged Parties",
    )
    tmfc043_affected_service_ids = fields.Many2many(
        comodel_name="tmf.service",
        relation="tmfc043_tt_service_rel",
        column1="ticket_id",
        column2="service_id",
        string="TMFC043 Affected Services",
    )

    def _tmfc043_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}
            if rec.partner_id:
                updates["tmfc043_related_partner_ids"] = [(6, 0, [rec.partner_id.id])]
            if rec.service_id:
                updates["tmfc043_affected_service_ids"] = [(6, 0, [rec.service_id.id])]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc043_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "partner_id" in vals or "service_id" in vals
        ):
            try:
                self._tmfc043_resolve_refs()
            except Exception:
                pass
        return res


class TMFC043ServiceProblem(models.Model):
    _inherit = "tmf.service.problem"

    tmfc043_related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc043_sp_partner_rel",
        column1="problem_id",
        column2="partner_id",
        string="TMFC043 Engaged Parties",
    )
    tmfc043_affected_service_ids = fields.Many2many(
        comodel_name="tmf.service",
        relation="tmfc043_sp_service_rel",
        column1="problem_id",
        column2="service_id",
        string="TMFC043 Affected Services",
    )
    tmfc043_affected_resource_ids = fields.Many2many(
        comodel_name="stock.lot",
        relation="tmfc043_sp_resource_rel",
        column1="problem_id",
        column2="resource_id",
        string="TMFC043 Affected Resources",
    )

    def _tmfc043_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Partner = self.env["res.partner"].sudo()
        Service = self.env["tmf.service"].sudo()
        Lot = self.env["stock.lot"].sudo()
        for rec in self:
            updates = {}
            party_ids = _extract_ids(_loads(rec.originator_party_json))
            if party_ids:
                partners = Partner.search([("tmf_id", "in", party_ids)])
                if partners:
                    updates["tmfc043_related_partner_ids"] = [(6, 0, partners.ids)]
            svc_ids = _extract_ids(_loads(rec.affected_service_json))
            if svc_ids:
                services = Service.search([("tmf_id", "in", svc_ids)])
                if services:
                    updates["tmfc043_affected_service_ids"] = [(6, 0, services.ids)]
            res_ids = _extract_ids(_loads(rec.affected_resource_json))
            if res_ids:
                lots = Lot.search([("tmf_id", "in", res_ids)])
                if lots:
                    updates["tmfc043_affected_resource_ids"] = [(6, 0, lots.ids)]
            if updates:
                rec.with_context(**ctx).write(updates)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc043_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and (
            "originator_party_json" in vals
            or "affected_service_json" in vals
            or "affected_resource_json" in vals
        ):
            try:
                self._tmfc043_resolve_refs()
            except Exception:
                pass
        return res


class TMFC043Alarm(models.Model):
    _inherit = "tmf.alarm"

    tmfc043_affected_service_ids = fields.Many2many(
        comodel_name="tmf.service",
        relation="tmfc043_alarm_service_rel",
        column1="alarm_id",
        column2="service_id",
        string="TMFC043 Affected Services",
    )

    def _tmfc043_resolve_refs(self):
        ctx = {"skip_tmf_wiring": True}
        Service = self.env["tmf.service"].sudo()
        for rec in self:
            svc_ids = _extract_ids(rec.affected_service)
            if svc_ids:
                services = Service.search([("tmf_id", "in", svc_ids)])
                if services:
                    rec.with_context(**ctx).write(
                        {"tmfc043_affected_service_ids": [(6, 0, services.ids)]}
                    )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc043_resolve_refs()
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring") and "affected_service" in vals:
            try:
                self._tmfc043_resolve_refs()
            except Exception:
                pass
        return res
