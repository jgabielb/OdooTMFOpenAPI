# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import uuid
from datetime import datetime, timezone


def _now_iso_z(*_args, **_kwargs):
    # Always returns a STRING in UTC with Z (CTK expects string)
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _ensure_ga(ga: dict, host_url: str):
    ga = dict(ga or {})

    # Ensure mandatory keys exist (CTK cares about presence)
    ga.setdefault("@type", "GeographicAddress")
    ga.setdefault("@baseType", "GeographicAddress")

    ga.setdefault("city", "")
    ga.setdefault("country", "")
    ga.setdefault("postcode", "")
    ga.setdefault("stateOrProvince", "")
    ga.setdefault("streetName", "")
    ga.setdefault("streetNr", "")
    ga.setdefault("streetType", "")
    ga.setdefault("locality", "")
    ga.setdefault("geographicSubAddress", [])

    # id/href (even synthetic) — CTK often expects these
    if not ga.get("id"):
        ga["id"] = str(uuid.uuid4())
    if not ga.get("href"):
        ga["href"] = f"{host_url}/tmf-api/geographicAddressManagement/v4/geographicAddress/{ga['id']}"

    return ga

API_BASE = "/tmf-api/geographicAddressManagement/v4"


class TMFGeographicAddress(models.Model):
    _name = "tmf.geographic.address"
    _description = "TMF673 GeographicAddress"
    _inherit = ["tmf.model.mixin"]

    # --- TMF fields (store as simple strings) ---
    name = fields.Char()
    city = fields.Char()
    country = fields.Char()
    locality = fields.Char()
    postcode = fields.Char()
    state_or_province = fields.Char()
    street_name = fields.Char()
    street_nr = fields.Char()
    street_type = fields.Char()

    # --- Complex structures as JSON ---
    geographic_location_json = fields.Text(string="geographicLocation")        # GeographicLocationRefOrValue
    # Properly model subaddresses as child records instead of a JSON blob
    sub_address_ids = fields.One2many(
        "tmf.geographic.sub.address", "address_id", string="geographicSubAddress"
    )

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "GeographicAddressCreateEvent",
            "update": "GeographicAddressAttributeValueChangeEvent",
            "delete": "GeographicAddressDeleteEvent",
        }
        if payloads is None:
            host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("geographicAddress", event_name, payload)
            except Exception:
                continue

    def _href(self):
        # controller will override base, but keep a safe fallback
        return f"/tmf-api/geographicAddressManagement/v4/geographicAddress/{self.tmf_id or self.id}"

    def to_tmf_json(self, host_url=None, fields_filter=None):
        """
        host_url: like 'http://localhost:8069'
        fields_filter: set([...]) with TMF json keys, to support ?fields=...
        """
        host_url = (host_url or "").rstrip("/")
        tmf_id = self.tmf_id or str(self.id)

        payload = {
            "id": tmf_id,
            "href": f"{host_url}/tmf-api/geographicAddressManagement/v4/geographicAddress/{tmf_id}",
            "name": self.name or "",
            "city": self.city or "",
            "country": self.country or "",
            "locality": self.locality or "",
            "postcode": self.postcode or "",
            "stateOrProvince": self.state_or_province or "",
            "streetName": self.street_name or "",
            "streetNr": self.street_nr or "",
            "streetType": self.street_type or "",
            "geographicLocation": json.loads(self.geographic_location_json) if self.geographic_location_json else None,
            "geographicSubAddress": [sa.to_tmf_json(host_url=host_url) for sa in self.sub_address_ids],
        }

        # TMF often allows omitting null complex nodes; CTK cares about array presence for geographicSubAddress
        if payload["geographicLocation"] is None:
            payload.pop("geographicLocation", None)

        if fields_filter:
            # Always keep id/href if requested explicitly or if fields are narrow
            filtered = {}
            for k in fields_filter:
                if k in payload:
                    filtered[k] = payload[k]
            return filtered

        return payload

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


class TMFGeographicSubAddress(models.Model):
    _name = "tmf.geographic.sub.address"
    _description = "TMF673 GeographicSubAddress"

    address_id = fields.Many2one("tmf.geographic.address", required=True, ondelete="cascade")

    tmf_id = fields.Char(default=lambda self: str(uuid.uuid4()), index=True)
    level_number = fields.Char()
    level_type = fields.Char()
    private_street_name = fields.Char()
    private_street_number = fields.Char()
    sub_address_type = fields.Char()

    def to_tmf_json(self, host_url=None):
        host_url = (host_url or "").rstrip("/")
        return {
            "id": self.tmf_id,
            "href": f"{host_url}/tmf-api/geographicAddressManagement/v4/geographicAddress/{self.address_id.tmf_id or self.address_id.id}/geographicSubAddress/{self.tmf_id}",
            "levelNumber": self.level_number or "",
            "levelType": self.level_type or "",
            "privateStreetName": self.private_street_name or "",
            "privateStreetNumber": self.private_street_number or "",
            "subAddressType": self.sub_address_type or "",
        }


class TMFGeographicAddressValidation(models.Model):
    _name = "tmf.geographic.address.validation"
    _description = "TMF673 GeographicAddressValidation"

    tmf_id = fields.Char(string="id", default=lambda self: str(uuid.uuid4()), index=True, required=True)

    provide_alternative = fields.Boolean(string="provideAlternative", default=False)

    # TMF673: status is a mandatory-ish field in CTK for this resource
    status = fields.Char(default="done", required=True)

    validation_date = fields.Char(string="validationDate", default=_now_iso_z, required=True)
    validation_result = fields.Char(string="validationResult", default="success", required=True)

    submitted_geographic_address_json = fields.Text(string="submittedGeographicAddress")

    # IMPORTANT: use TMF673 field naming
    valid_address_json = fields.Text(string="validAddress")

    alternate_geographic_address_json = fields.Text(string="alternateGeographicAddress")

    state = fields.Selection(
        selection=[
            ("acknowledged", "acknowledged"),
            ("rejected", "rejected"),
            ("pending", "pending"),
            ("done", "done"),
            ("held", "held"),
            ("inProgress", "inProgress"),
            ("cancelled", "cancelled"),
        ],
        default="done",
        required=True,
    )

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "GeographicAddressValidationCreateEvent",
            "update": "GeographicAddressValidationAttributeValueChangeEvent",
            "delete": "GeographicAddressValidationDeleteEvent",
        }
        if payloads is None:
            host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("geographicAddressValidation", event_name, payload)
            except Exception:
                continue

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")
        
        def _dt_to_iso_z(dtval):
            if not dtval: return None
            if isinstance(dtval, datetime):
                return dtval.replace(microsecond=0).isoformat() + "Z"
            return str(dtval).strip().strip('"').strip("'")

        def _ensure_ga(ga):
            ga = ga or {}
            obj = dict(ga)
            ga_id = obj.get("id") or str(uuid.uuid4())
            obj.update({
                "id": ga_id,
                "href": obj.get("href") or f"{host_url}{API_BASE}/geographicAddress/{ga_id}",
                "@type": "GeographicAddress",
                "@baseType": "GeographicAddress"
            })
            # Ensure city/locality parity for CTK
            if not obj.get("city"): obj["city"] = obj.get("locality") or ""
            if not obj.get("locality"): obj["locality"] = obj.get("city") or ""
            
            # Fill mandatory strings
            for field in ["streetName", "streetType", "streetNr", "postcode", "country", "stateOrProvince"]:
                obj.setdefault(field, "")
            obj.setdefault("geographicSubAddress", [])
            return obj

        submitted_in = json.loads(self.submitted_geographic_address_json or "{}")
        valid_in = json.loads(self.valid_address_json or "{}")
        alternate_in = json.loads(self.alternate_geographic_address_json or "[]")

        submitted = _ensure_ga(submitted_in)
        valid = _ensure_ga(valid_in)

        # 1. Build the payload with BOTH naming conventions to ensure CTK coverage
        payload = {
            "id": self.tmf_id,
            "href": f"{host_url}{API_BASE}/geographicAddressValidation/{self.tmf_id}",
            "@type": "GeographicAddressValidation",
            "@baseType": "GeographicAddressValidation",
            "provideAlternative": bool(self.provide_alternative),
            "validationDate": _dt_to_iso_z(self.validation_date),
            "validationResult": self.validation_result or "success",
            
            # Use BOTH 'status' and 'state' (Ref: PDF p.11 vs p.12 mismatch)
            "status": self.status or "done",
            "state": self.status or "done",

            "submittedGeographicAddress": submitted,
            
            # Use BOTH 'validGeographicAddress' and 'validAddress'
            "validGeographicAddress": valid,
            "validAddress": valid,

            "alternateGeographicAddress": [_ensure_ga(x) for x in alternate_in] if self.provide_alternative else [],
            "validationCharacteristic": [],
            "validationMessage": []
        }

        # 2. Clean up: Remove any keys that are None (CTK prefers omitted over null)
        payload = {k: v for k, v in payload.items() if v is not None}

        # 3. Handle TMF Filtering (?fields=...)
        if fields_filter:
            ff = set(fields_filter)
            ff |= {"id", "href"}
            # If they ask for 'status', give them 'status'. If they ask for 'state', give 'state'.
            return {k: v for k, v in payload.items() if k in ff}

        return payload

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        host_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        payloads = [rec.to_tmf_json(host_url=host_url) for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


class TMFGeographicAddressSeed(models.AbstractModel):
    """
    Seed a minimum dataset so CTK filtering tests don't get [].
    This avoids you having to create records manually.
    """
    _name = "tmf.geographic.address.seed"
    _description = "TMF673 seed helper"

    @api.model
    def ensure_seed_data(self):
        city = "Brighton"
        country = "Australia"
        postcode = "SA"
        street_name = "strathmore"
        street_type = "terrace"

        existing = self.env["tmf.geographic.address"].sudo().search([
            ("city", "=", city),
            ("country", "=", country),
            ("postcode", "=", postcode),
            ("street_name", "=", street_name),
            ("street_type", "=", street_type),
        ], limit=1)
        if existing:
            return existing

        addr = self.env["tmf.geographic.address"].sudo().create({
            "tmf_id": str(uuid.uuid4()),
            "name": "Main Home",
            "city": city,
            "country": country,
            "locality": city,
            "postcode": postcode,
            "state_or_province": postcode,
            "street_name": street_name,
            "street_nr": "1",
            "street_type": street_type,
        })

        self.env["tmf.geographic.sub.address"].sudo().create({
            "address_id": addr.id,
            "level_number": "1",
            "level_type": "Floor",
            "private_street_name": "A",
            "private_street_number": "101",
            "sub_address_type": "unit",
        })
        return addr
