import json
from datetime import datetime, timezone
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None}


class TMFDigitalIdentity(models.Model):
    _name = "tmf.digital.identity"
    _description = "TMF720 DigitalIdentity"
    _inherit = ["tmf.model.mixin"]

    creation_date = fields.Char(string="creationDate")
    last_update = fields.Char(string="lastUpdate")
    nickname = fields.Char(string="nickname")
    status = fields.Char(string="status")

    attachment_json = fields.Text(string="attachment")
    contact_medium_json = fields.Text(string="contactMedium")
    credential_json = fields.Text(string="credential")
    individual_identified_json = fields.Text(string="individualIdentified")
    party_role_identified_json = fields.Text(string="partyRoleIdentified")
    related_party_json = fields.Text(string="relatedParty")
    resource_identified_json = fields.Text(string="resourceIdentified")
    valid_for_json = fields.Text(string="validFor")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/digitalIdentityManagement/v4/digitalIdentity"

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "creationDate": self.creation_date or self._now_iso(),
            "lastUpdate": self.last_update or self.creation_date or self._now_iso(),
            "nickname": self.nickname,
            "status": self.status or "active",
            "attachment": _loads(self.attachment_json),
            "contactMedium": _loads(self.contact_medium_json),
            "credential": _loads(self.credential_json),
            "individualIdentified": _loads(self.individual_identified_json),
            "partyRoleIdentified": _loads(self.party_role_identified_json),
            "relatedParty": _loads(self.related_party_json),
            "resourceIdentified": _loads(self.resource_identified_json),
            "validFor": _loads(self.valid_for_json),
            "@type": self.tmf_type_value or "DigitalIdentity",
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("creationDate", "creation_date"),
            ("lastUpdate", "last_update"),
            ("nickname", "nickname"),
            ("status", "status"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("attachment", "attachment_json"),
            ("contactMedium", "contact_medium_json"),
            ("credential", "credential_json"),
            ("individualIdentified", "individual_identified_json"),
            ("partyRoleIdentified", "party_role_identified_json"),
            ("relatedParty", "related_party_json"),
            ("resourceIdentified", "resource_identified_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="digitalIdentity",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            created = vals.get("creation_date") or self._now_iso()
            vals.setdefault("creation_date", created)
            vals.setdefault("last_update", vals.get("last_update") or created)
            vals.setdefault("status", vals.get("status") or "active")
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="digitalIdentity",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
