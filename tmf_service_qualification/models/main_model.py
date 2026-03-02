# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import logging
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)


def _now_iso_z():
    # TMF examples use Z; keep it simple.
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ServiceQualification(models.Model):
    _name = "tmf.service.qualification"
    _description = "TMF645 Service Qualification (Check/Query)"
    _inherit = ["tmf.model.mixin"]

    # -------------------------
    # TMF645 discriminator
    # -------------------------
    qualification_kind = fields.Selection(
        [
            ("check", "CheckServiceQualification"),
            ("query", "QueryServiceQualification"),
        ],
        default="check",
        required=True,
        index=True,
    )

    # -------------------------
    # TMF645 top-level fields
    # -------------------------
    description = fields.Text(string="Description")
    external_id = fields.Char(string="externalId", index=True)

    check_service_qualification_date = fields.Datetime(string="checkServiceQualificationDate")
    query_service_qualification_date = fields.Datetime(string="queryServiceQualificationDate")

    expected_qualification_date = fields.Datetime(string="expectedQualificationDate")
    estimated_response_date = fields.Datetime(string="estimatedResponseDate")
    effective_qualification_date = fields.Datetime(string="effectiveQualificationDate")
    expiration_date = fields.Datetime(string="expirationDate")

    instant_sync_qualification = fields.Boolean(string="instantSyncQualification", default=False)
    provide_alternative = fields.Boolean(string="provideAlternative", default=False)
    provide_unavailability_reason = fields.Boolean(string="provideUnavailabilityReason", default=False)

    state = fields.Selection(
        [
            ("acknowledged", "Acknowledged"),
            ("inProgress", "In Progress"),
            ("terminatedWithError", "Terminated With Error"),
            ("done", "Done"),
        ],
        default="acknowledged",
        string="state",
        index=True,
    )

    # Resource-level qualificationResult (qualified | alternate | unqualified)
    qualification_result = fields.Selection(
        [
            ("qualified", "Qualified"),
            ("alternate", "Alternate"),
            ("unqualified", "Unqualified"),
        ],
        string="qualificationResult",
        readonly=True,
    )

    # -------------------------
    # Storage for complex structures
    # (keeps implementation small but still compliant at API shape level)
    # -------------------------
    service_qualification_item_json = fields.Text(string="serviceQualificationItem (json)")
    related_party_json = fields.Text(string="relatedParty (json)")
    search_criteria_json = fields.Text(string="searchCriteria (json)")

    # Convenience links (optional; used by your current feasibility demo logic)
    place_id = fields.Many2one("tmf.geographic.address", string="Service Address")
    service_specification_id = fields.Many2one("tmf.product.specification", string="Service Specification")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Draft Sale Order", ondelete="set null")

    def _safe_json_load(self, value, default):
        if value in (None, False, ""):
            return default
        if isinstance(value, (list, dict)):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, type(default)) else default
        except Exception:
            return default

    def _resolve_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        if self.partner_id and self.partner_id.exists():
            return self.partner_id
        parties = self._safe_json_load(self.related_party_json, [])
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            pname = party.get("name")
            if pid:
                partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
                if not partner and str(pid).isdigit():
                    partner = Partner.browse(int(pid))
                if partner and partner.exists():
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
        return Partner.browse([])

    def _resolve_product_template(self):
        self.ensure_one()
        if self.product_tmpl_id and self.product_tmpl_id.exists():
            return self.product_tmpl_id
        if self.service_specification_id and hasattr(self.service_specification_id, "product_tmpl_id"):
            tmpl = self.service_specification_id.product_tmpl_id
            if tmpl and tmpl.exists():
                return tmpl
        return self.env["product.template"]

    def _sync_odoo_links(self):
        SaleOrder = self.env["sale.order"].sudo()
        for rec in self:
            partner = rec._resolve_partner()
            if partner and partner.exists() and rec.partner_id != partner:
                rec.partner_id = partner.id

            tmpl = rec._resolve_product_template()
            if tmpl and tmpl.exists() and rec.product_tmpl_id != tmpl:
                rec.product_tmpl_id = tmpl.id

            try:
                if rec.sale_order_id and rec.sale_order_id.exists():
                    continue
                if not rec.partner_id:
                    continue
                so = SaleOrder.search(
                    [("partner_id", "=", rec.partner_id.id), ("state", "=", "draft"), ("client_order_ref", "=", rec.tmf_id)],
                    limit=1,
                )
                if not so:
                    so = SaleOrder.create(
                        {
                            "partner_id": rec.partner_id.id,
                            "client_order_ref": rec.tmf_id,
                            "origin": f"TMF645:{rec.tmf_id}",
                        }
                    )
                rec.sale_order_id = so.id
            except Exception:
                pass

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ServiceQualificationCreateEvent",
            "update": "ServiceQualificationAttributeValueChangeEvent",
            "delete": "ServiceQualificationDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("serviceQualification", event_name, payload)
            except Exception:
                continue

    # -------------------------
    # Paths
    # -------------------------
    def _get_tmf_api_path(self):
        if self.qualification_kind == "query":
            return "/tmf-api/serviceQualificationManagement/v4/queryServiceQualification"
        return "/tmf-api/serviceQualificationManagement/v4/checkServiceQualification"

    # -------------------------
    # Create defaults aligned to TMF lifecycle
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            # Set submit timestamp according to resource kind
            if vals.get("qualification_kind") == "query":
                vals.setdefault("query_service_qualification_date", now)
            else:
                vals.setdefault("check_service_qualification_date", now)

            # Default task state per guide
            vals.setdefault("state", "acknowledged")

        recs = super().create(vals_list)
        recs._sync_odoo_links()

        # If sync requested, complete immediately
        for rec in recs:
            if rec.qualification_kind == "check":
                if rec.instant_sync_qualification:
                    rec._run_feasibility_check()
            else:
                # Query: for now, mark done immediately if sync requested
                if rec.instant_sync_qualification:
                    rec._run_query_resolution()

        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if any(
            k in vals
            for k in (
                "related_party_json",
                "partner_id",
                "service_specification_id",
                "product_tmpl_id",
                "sale_order_id",
            )
        ):
            self._sync_odoo_links()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res

    # -------------------------
    # Demo feasibility logic for CHECK
    # -------------------------
    def _run_feasibility_check(self):
        self.ensure_one()
        self.state = "inProgress"

        # Very simple demo logic: only Santiago qualifies
        city = (self.place_id.city or "") if self.place_id else ""
        if "Santiago" in city:
            item_result = "qualified"
            reason = []
        else:
            item_result = "unqualified"
            reason = [{"code": "COVERAGE-001", "label": f"No coverage available in {city}"}]

        # Item JSON: ensure we return per-item qualificationResult and optionally reasons
        items = self._get_items()
        if not items:
            # Should never happen if controller validated, but keep safe
            items = [{"id": "1", "service": {}}]

        for it in items:
            it["state"] = "done"
            it["qualificationResult"] = item_result
            if self.provide_unavailability_reason and item_result != "qualified":
                it["eligibilityUnavailabilityReason"] = reason
            else:
                it.pop("eligibilityUnavailabilityReason", None)

        # Resource-level result
        self.qualification_result = item_result
        self.effective_qualification_date = fields.Datetime.now()
        self.expiration_date = fields.Datetime.add(fields.Datetime.now(), days=7)
        self.state = "done"

        self._set_items(items)

    # -------------------------
    # Minimal QUERY resolution scaffold
    # -------------------------
    def _run_query_resolution(self):
        self.ensure_one()
        self.state = "inProgress"

        # For now: echo searchCriteria and return 0..N serviceQualificationItem if you later implement catalog lookup.
        # Spec says: if none available, return no items and no error.
        items = self._get_items() or []
        self._set_items(items)

        self.qualification_result = None
        self.effective_qualification_date = fields.Datetime.now()
        self.expiration_date = fields.Datetime.add(fields.Datetime.now(), days=2)
        self.state = "done"

    # -------------------------
    # JSON helpers
    # -------------------------
    def _get_items(self):
        if not self.service_qualification_item_json:
            return []
        try:
            return json.loads(self.service_qualification_item_json) or []
        except Exception:
            return []

    def _set_items(self, items):
        self.service_qualification_item_json = json.dumps(items, ensure_ascii=False)

    def _get_related_party(self):
        if not self.related_party_json:
            return []
        try:
            return json.loads(self.related_party_json) or []
        except Exception:
            return []

    def _get_search_criteria(self):
        if not self.search_criteria_json:
            return None
        try:
            return json.loads(self.search_criteria_json)
        except Exception:
            return None

    # -------------------------
    # TMF serialization
    # -------------------------
    def to_tmf_json(self):
        self.ensure_one()

        base = {
            "id": self.tmf_id or str(self.id),
            "href": self.href,
            "description": self.description,
            "externalId": self.external_id,
            "instantSyncQualification": bool(self.instant_sync_qualification),
            "state": self.state,
            "expectedQualificationDate": self.expected_qualification_date.isoformat() if self.expected_qualification_date else None,
            "estimatedResponseDate": self.estimated_response_date.isoformat() if self.estimated_response_date else None,
            "effectiveQualificationDate": self.effective_qualification_date.isoformat() if self.effective_qualification_date else None,
            "expirationDate": self.expiration_date.isoformat() if self.expiration_date else None,
            "relatedParty": self._get_related_party(),
            "@type": "QueryServiceQualification" if self.qualification_kind == "query" else "CheckServiceQualification",
        }

        if self.qualification_kind == "query":
            base["queryServiceQualificationDate"] = (
                self.query_service_qualification_date.isoformat() if self.query_service_qualification_date else None
            )
            base["searchCriteria"] = self._get_search_criteria()
            base["serviceQualificationItem"] = self._get_items()
        else:
            base["checkServiceQualificationDate"] = (
                self.check_service_qualification_date.isoformat() if self.check_service_qualification_date else None
            )
            base["provideAlternative"] = bool(self.provide_alternative)
            base["provideUnavailabilityReason"] = bool(self.provide_unavailability_reason)
            base["qualificationResult"] = self.qualification_result
            base["serviceQualificationItem"] = self._get_items()

        return base
