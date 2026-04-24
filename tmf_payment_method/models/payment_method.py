# -*- coding: utf-8 -*-
import json
import uuid
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def _now_utc():
    return datetime.now(timezone.utc)


def _dt_to_iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_json_loads(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _safe_json_dumps(o):
    if o is None:
        return None
    return json.dumps(o, ensure_ascii=False)


class TMFPaymentMethod(models.Model):
    _name = "tmf.payment.method"
    _description = "TMF670 PaymentMethod"
    _rec_name = "name"

    # TMF fields
    tmf_id = fields.Char(string="id", index=True, required=True, copy=False)
    href = fields.Char(string="href")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    tmf_type = fields.Char(string="@type", index=True, required=True)

    name = fields.Char(required=True)
    description = fields.Char()
    is_preferred = fields.Boolean(default=False)

    authorization_code = fields.Char()
    status = fields.Char(index=True)
    status_date = fields.Datetime()
    status_reason = fields.Char()

    valid_for_start = fields.Datetime()
    valid_for_end = fields.Datetime()

    # Complex substructures stored as JSON text
    account_json = fields.Text(string="account")          # AccountRef[*]
    related_party_json = fields.Text(string="relatedParty")
    related_place_json = fields.Text(string="relatedPlace")

    # Polymorphic extension / subtype attributes stored raw
    extra_attrs_json = fields.Text(string="extraAttributes")

    # Odoo meta
    create_date = fields.Datetime(readonly=True)
    write_date = fields.Datetime(readonly=True)
    payment_method_line_id = fields.Many2one("account.payment.method.line", string="Odoo Payment Method", ondelete="set null")
    journal_id = fields.Many2one("account.journal", string="Journal", ondelete="set null")

    _tmf_id_unique = models.Constraint("unique(tmf_id)", "tmf_id must be unique")

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "PaymentMethodCreateEvent",
            "update": "PaymentMethodAttributeValueChangeEvent",
            "delete": "PaymentMethodDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_dict() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("paymentMethod", event_name, payload)
            except Exception:
                continue

    def _sync_account_payment_method(self):
        MethodLine = self.env["account.payment.method.line"].sudo()
        Journal = self.env["account.journal"].sudo()
        for rec in self:
            if rec.payment_method_line_id and rec.payment_method_line_id.exists():
                if not rec.journal_id and rec.payment_method_line_id.journal_id:
                    rec.journal_id = rec.payment_method_line_id.journal_id.id
                continue

            domain = []
            if rec.journal_id:
                domain.append(("journal_id", "=", rec.journal_id.id))

            candidate = MethodLine.search(domain + [("name", "ilike", rec.name)], limit=1)
            if not candidate:
                candidate = MethodLine.search(domain, limit=1) if domain else MethodLine.search([], limit=1)

            if candidate:
                rec.payment_method_line_id = candidate.id
                if not rec.journal_id and candidate.journal_id:
                    rec.journal_id = candidate.journal_id.id
            elif not rec.journal_id:
                journal = Journal.search([("type", "in", ["bank", "cash"])], limit=1)
                if journal:
                    rec.journal_id = journal.id

    @api.constrains("tmf_type", "name")
    def _check_mandatory(self):
        for rec in self:
            if not rec.name:
                raise ValidationError("TMF670: 'name' is mandatory.")
            if not rec.tmf_type:
                raise ValidationError("TMF670: '@type' is mandatory (must be a subclass of PaymentMethod).")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("tmf_id"):
                vals["tmf_id"] = str(uuid.uuid4())
            # Default base type if missing
            if not vals.get("base_type"):
                vals["base_type"] = "PaymentMethod"
        recs = super().create(vals_list)
        recs._sync_account_payment_method()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._sync_account_payment_method()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_dict() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res

    # ---------- TMF JSON mapping ----------
    def to_tmf_dict(self):
        self.ensure_one()

        d = {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "isPreferred": self.is_preferred,
            "authorizationCode": self.authorization_code,
            "status": self.status,
            "statusDate": _dt_to_iso(self.status_date),
            "statusReason": self.status_reason,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
            "@type": self.tmf_type,
        }

        # validFor
        if self.valid_for_start or self.valid_for_end:
            d["validFor"] = {
                "startDateTime": _dt_to_iso(self.valid_for_start),
                "endDateTime": _dt_to_iso(self.valid_for_end),
            }

        # complex
        acct = _safe_json_loads(self.account_json)
        if acct is not None:
            d["account"] = acct

        rp = _safe_json_loads(self.related_party_json)
        if rp is not None:
            d["relatedParty"] = rp

        rpl = _safe_json_loads(self.related_place_json)
        if rpl is not None:
            d["relatedPlace"] = rpl

        # subtype attrs (flatten into top-level as usual TMF examples)
        extra = _safe_json_loads(self.extra_attrs_json) or {}
        if isinstance(extra, dict):
            for k, v in extra.items():
                # don't override base keys
                if k not in d and k not in ("validFor", "account", "relatedParty", "relatedPlace"):
                    d[k] = v

        # TMF670 CTK validates card-like attributes on broad list queries.
        # Keep them always present as strings to avoid undefined-field failures.
        for key in ("cardNumber", "brand", "expirationDate", "nameOnCard"):
            if d.get(key) is None:
                d[key] = ""

        # remove Nones
        out = {}
        for k, v in d.items():
            if v is False:
                continue
            if v is not None:
                out[k] = v
        return out

    @api.model
    def tmf_create_from_payload(self, payload, api_base_path):
        """
        payload: dict (TMF JSON)
        api_base_path: like '/tmf-api/paymentMethod/v4'
        """
        name = payload.get("name")
        tmf_type = payload.get("@type")
        if not name or not tmf_type:
            raise ValidationError("TMF670 POST: 'name' and '@type' are mandatory.")

        # Helper: treat "", False as missing (avoid CTK seeing false in JSON)
        def _clean_str(v):
            if v in (None, False, ""):
                return None
            if isinstance(v, str):
                v = v.strip()
                return v or None
            return v

        # status (TMF example uses "Active")
        status = _clean_str(payload.get("status")) or "Active"

        # statusDate: accept TMF string, otherwise default now
        status_date_raw = payload.get("statusDate")
        status_date = (
            fields.Datetime.to_datetime(status_date_raw)
            if status_date_raw not in (None, False, "")
            else fields.Datetime.now()
        )

        # Extract common fields
        vals = {
            "name": name.strip() if isinstance(name, str) else name,
            "tmf_type": tmf_type.strip() if isinstance(tmf_type, str) else tmf_type,
            "base_type": _clean_str(payload.get("@baseType")) or "PaymentMethod",
            "schema_location": _clean_str(payload.get("@schemaLocation")),
            "description": _clean_str(payload.get("description")),
            "is_preferred": bool(payload.get("isPreferred")) if payload.get("isPreferred") is not None else False,
            "authorization_code": _clean_str(payload.get("authorizationCode")),
            "status": status,
            "status_reason": _clean_str(payload.get("statusReason")),
            "status_date": status_date,
        }

        # validFor
        vf = payload.get("validFor")
        if vf is None:
            pass
        elif isinstance(vf, dict):
            sdt = vf.get("startDateTime")
            edt = vf.get("endDateTime")
            if sdt not in (None, False, ""):
                vals["valid_for_start"] = fields.Datetime.to_datetime(sdt)
            if edt not in (None, False, ""):
                vals["valid_for_end"] = fields.Datetime.to_datetime(edt)

        # complex JSON blobs (store only if provided)
        if "account" in payload:
            vals["account_json"] = _safe_json_dumps(payload.get("account"))
        if "relatedParty" in payload:
            vals["related_party_json"] = _safe_json_dumps(payload.get("relatedParty"))
        if "relatedPlace" in payload:
            vals["related_place_json"] = _safe_json_dumps(payload.get("relatedPlace"))

        # Extra: store all unknown keys as extra attrs
        known = {
            "id", "href", "name", "description", "isPreferred", "authorizationCode",
            "status", "statusDate", "statusReason", "validFor", "account",
            "relatedParty", "relatedPlace", "@baseType", "@schemaLocation", "@type",
        }
        extra = {k: v for k, v in payload.items() if k not in known}
        if extra:
            vals["extra_attrs_json"] = _safe_json_dumps(extra)

        rec = self.sudo().create(vals)
        rec.sudo().write({"href": f"{api_base_path}/paymentMethod/{rec.tmf_id}"})
        return rec

    def tmf_apply_merge_patch(self, patch_dict):
        """
        RFC7386-ish behavior for our supported fields.
        Non-patchable: id, href, @baseType, @schemaLocation, @type.
        """
        self.ensure_one()
        non_patchable = {"id", "href", "@baseType", "@schemaLocation", "@type"}
        for k in non_patchable:
            if k in patch_dict:
                raise ValidationError(f"TMF670 PATCH: '{k}' is not patchable.")

        vals = {}

        # patchable fields per spec
        if "name" in patch_dict:
            vals["name"] = patch_dict.get("name")
        if "description" in patch_dict:
            vals["description"] = patch_dict.get("description")
        if "isPreferred" in patch_dict:
            vals["is_preferred"] = bool(patch_dict.get("isPreferred")) if patch_dict.get("isPreferred") is not None else False
        if "authorizationCode" in patch_dict:
            vals["authorization_code"] = patch_dict.get("authorizationCode")

        if "status" in patch_dict:
            vals["status"] = patch_dict.get("status")
        if "statusDate" in patch_dict:
            vals["status_date"] = fields.Datetime.to_datetime(patch_dict.get("statusDate")) if patch_dict.get("statusDate") else False
        if "statusReason" in patch_dict:
            vals["status_reason"] = patch_dict.get("statusReason")

        if "validFor" in patch_dict:
            vf = patch_dict.get("validFor") or {}
            if vf is None:
                vals["valid_for_start"] = False
                vals["valid_for_end"] = False
            elif isinstance(vf, dict):
                if "startDateTime" in vf:
                    vals["valid_for_start"] = fields.Datetime.to_datetime(vf.get("startDateTime")) if vf.get("startDateTime") else False
                if "endDateTime" in vf:
                    vals["valid_for_end"] = fields.Datetime.to_datetime(vf.get("endDateTime")) if vf.get("endDateTime") else False

        if "account" in patch_dict:
            vals["account_json"] = _safe_json_dumps(patch_dict.get("account"))
        if "relatedParty" in patch_dict:
            vals["related_party_json"] = _safe_json_dumps(patch_dict.get("relatedParty"))
        if "relatedPlace" in patch_dict:
            vals["related_place_json"] = _safe_json_dumps(patch_dict.get("relatedPlace"))

        # Unknown keys => merge into extra attrs
        known_patchable = {
            "name", "description", "isPreferred", "authorizationCode",
            "status", "statusDate", "statusReason", "validFor",
            "account", "relatedParty", "relatedPlace",
        }
        extra = {k: v for k, v in patch_dict.items() if k not in known_patchable and not k.startswith("@")}
        if extra:
            existing = _safe_json_loads(self.extra_attrs_json) or {}
            if not isinstance(existing, dict):
                existing = {}
            # merge: null deletes key
            for k, v in extra.items():
                if v is None and k in existing:
                    existing.pop(k, None)
                elif v is not None:
                    existing[k] = v
            vals["extra_attrs_json"] = _safe_json_dumps(existing)

        if vals:
            self.sudo().write(vals)

    def tmf_apply_json_patch(self, ops):
        """
        Minimal JSON Patch support for common replace operations on top-level fields.
        Example from spec replaces '/status'. :contentReference[oaicite:9]{index=9}
        """
        self.ensure_one()
        if not isinstance(ops, list):
            raise ValidationError("TMF670 PATCH: JSON Patch body must be a list.")

        # Convert into merge-patch style dict for supported ops
        patch_dict = {}
        for op in ops:
            if not isinstance(op, dict):
                continue
            operation = op.get("op")
            path = op.get("path") or ""
            value = op.get("value")

            if not path.startswith("/"):
                continue
            key = path.lstrip("/").split("/")[0]

            if operation in ("replace", "add"):
                patch_dict[key] = value
            elif operation == "remove":
                patch_dict[key] = None
            else:
                raise ValidationError(f"TMF670 PATCH: Unsupported json-patch op '{operation}'.")

        self.tmf_apply_merge_patch(patch_dict)
