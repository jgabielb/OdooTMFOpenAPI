# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import uuid


class TMFGeographicSite(models.Model):
    _name = "tmf.geographic.site"
    _description = "GeographicSite"
    _inherit = ["tmf.model.mixin"]  # assumes provides tmf_id + href

    code = fields.Char(string="code")
    description = fields.Char(string="description")
    name = fields.Char(string="name")
    status = fields.Char(string="status")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    geographic_address_id = fields.Many2one("tmf.geographic.address", string="Geographic Address", ondelete="set null")
    stock_location_id = fields.Many2one("stock.location", string="Stock Location", ondelete="set null")

    # Store complex sub-resources as JSON text (not Char)
    calendar_json = fields.Text(string="calendar")
    place_json = fields.Text(string="place")
    related_party_json = fields.Text(string="relatedParty")
    site_relationship_json = fields.Text(string="siteRelationship")

    def _get_tmf_api_path(self):
        # Spec path uses /geographicSiteManagement/v4/geographicSite
        return "/tmf-api/geographicSiteManagement/v4/geographicSite"

    # -------------------------
    # JSON helpers
    # -------------------------
    def _json_load(self, value):
        if not value:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            # keep raw if invalid
            return value

    def _json_dump(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            # assume already serialized JSON
            return value
        return json.dumps(value, ensure_ascii=False)

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        if self.partner_id and self.partner_id.exists():
            return self.partner_id
        related = self._json_load(self.related_party_json)
        items = related if isinstance(related, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = item.get("id")
            pname = item.get("name")
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

    def _resolve_geographic_address_from_place(self):
        self.ensure_one()
        Address = self.env["tmf.geographic.address"].sudo()
        if self.geographic_address_id and self.geographic_address_id.exists():
            return self.geographic_address_id
        place = self._json_load(self.place_json)
        items = place if isinstance(place, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = item.get("id")
            if not pid:
                continue
            address = Address.search([("tmf_id", "=", str(pid))], limit=1)
            if address:
                return address
            if str(pid).isdigit():
                address = Address.browse(int(pid))
                if address.exists():
                    return address
        return Address.browse([])

    def _resolve_stock_location(self):
        self.ensure_one()
        Location = self.env["stock.location"].sudo()
        if self.stock_location_id and self.stock_location_id.exists():
            return self.stock_location_id
        if self.name:
            location = Location.search([("name", "=", self.name)], limit=1)
            if location:
                return location
        return Location.browse([])

    def _sync_links(self):
        for rec in self:
            partner = rec._resolve_partner_from_related_party()
            if partner and partner.exists() and rec.partner_id != partner:
                rec.partner_id = partner.id
            address = rec._resolve_geographic_address_from_place()
            if address and address.exists() and rec.geographic_address_id != address:
                rec.geographic_address_id = address.id
            location = rec._resolve_stock_location()
            if location and location.exists() and rec.stock_location_id != location:
                rec.stock_location_id = location.id

    # -------------------------
    # TMF serialization
    # -------------------------
    def to_tmf_json(self):

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        api_path = "/tmf-api/geographicSiteManagement/v4/geographicSite"
        href = self.href or (f"{base_url}{api_path}/{self.tmf_id}" if base_url and self.tmf_id else None)
        tmf_id = fields.Char(default=lambda self: str(uuid.uuid4()), index=True, readonly=True)

        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": href,
            "@type": "GeographicSite",
            "code": self.code,
            "description": self.description,
            "name": self.name,
            "status": self.status,
        }

        cal = self._json_load(self.calendar_json)
        if cal is not None:
            payload["calendar"] = cal

        place = self._json_load(self.place_json)
        if place is not None:
            payload["place"] = place

        rp = self._json_load(self.related_party_json)
        if rp is not None:
            payload["relatedParty"] = rp

        rel = self._json_load(self.site_relationship_json)
        if rel is not None:
            payload["siteRelationship"] = rel

        return payload

    # -------------------------
    # TMF674 validations (based on user guide rules)
    # -------------------------
    def _validate_create_payload(self, payload: dict):
       
        # calendar: if present, each item must have status
        cal = payload.get("calendar")
        if cal is not None:
            if not isinstance(cal, list):
                raise ValidationError("TMF674 POST: 'calendar' must be a list.")
            for idx, item in enumerate(cal):
                if not isinstance(item, dict):
                    raise ValidationError(f"TMF674 POST: calendar[{idx}] must be an object.")
                if not item.get("status"):
                    raise ValidationError("TMF674 POST: 'calendar.status' is mandatory when calendar is provided.")

        # place rule: "id and @referredType OR @type and valued place"
        # (we accept the user guide style examples)
        place = payload.get("place")
        if place is not None:
            if not isinstance(place, list):
                raise ValidationError("TMF674 POST: 'place' must be a list.")
            for idx, p in enumerate(place):
                if not isinstance(p, dict):
                    raise ValidationError(f"TMF674 POST: place[{idx}] must be an object.")

                has_ref = bool(p.get("id") and p.get("@referredType"))
                has_valued = bool(p.get("@type"))  # valued place typically has @type like GeographicAddress
                if not (has_ref or has_valued):
                    raise ValidationError(
                        "TMF674 POST: each place item must include (id and @referredType) OR (@type and valued place)."
                    )

        # relatedParty: if present, each item needs id and @referredType
        rp = payload.get("relatedParty")
        if rp is not None:
            if not isinstance(rp, list):
                raise ValidationError("TMF674 POST: 'relatedParty' must be a list.")
            for idx, r in enumerate(rp):
                if not isinstance(r, dict):
                    raise ValidationError(f"TMF674 POST: relatedParty[{idx}] must be an object.")
                if not r.get("id") or not r.get("@referredType"):
                    raise ValidationError("TMF674 POST: relatedParty requires 'id' and '@referredType'.")

        # siteRelationship: if present, each needs id and relationshipType
        sr = payload.get("siteRelationship")
        if sr is not None:
            if not isinstance(sr, list):
                raise ValidationError("TMF674 POST: 'siteRelationship' must be a list.")
            for idx, s in enumerate(sr):
                if not isinstance(s, dict):
                    raise ValidationError(f"TMF674 POST: siteRelationship[{idx}] must be an object.")
                if not s.get("id") or not s.get("relationshipType"):
                    raise ValidationError("TMF674 POST: siteRelationship requires 'id' and 'relationshipType'.")

    # -------------------------
    # Odoo create/write/unlink with notifications
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_links()
        for rec in recs:
            rec._notify("geographicSite", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ("name", "related_party_json", "place_json", "partner_id", "geographic_address_id", "stock_location_id")):
            self._sync_links()
        for rec in self:
            rec._notify("geographicSite", "attributeValueChange", rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="geographicSite",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
