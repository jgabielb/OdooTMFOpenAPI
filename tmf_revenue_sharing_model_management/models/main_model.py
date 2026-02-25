import json
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
    return {k: v for k, v in payload.items() if v is not None and v is not False}


class TMFPartyRevSharingModel(models.Model):
    _name = "tmf.party.rev.sharing.model"
    _description = "TMF738 PartyRevSharingModel"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    state = fields.Char(string="state")
    lifecycle_status = fields.Char(string="lifecycleStatus")

    related_party_json = fields.Text(string="relatedParty")
    party_rev_sharing_model_item_json = fields.Text(string="partyRevSharingModelItem")
    product_specification_json = fields.Text(string="productSpecification")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/revenueSharingModelManagement/v5/partyRevSharingModel"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "state": self.state,
            "lifecycleStatus": self.lifecycle_status,
            "relatedParty": _loads(self.related_party_json),
            "partyRevSharingModelItem": _loads(self.party_rev_sharing_model_item_json),
            "productSpecification": _loads(self.product_specification_json),
            "@type": self.tmf_type_value or "PartyRevSharingModel",
            "@baseType": self.base_type or "PartyRevSharingModel",
            "@schemaLocation": self.schema_location or "https://tmforum.org/schema",
        }
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("state", "state"),
            ("lifecycleStatus", "lifecycle_status"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("relatedParty", "related_party_json"),
            ("partyRevSharingModelItem", "party_rev_sharing_model_item_json"),
            ("productSpecification", "product_specification_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="partyRevSharingModel",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "lifecycle_status" in vals
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
                    api_name="partyRevSharingModel",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
