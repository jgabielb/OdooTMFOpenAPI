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


class TMFPartyRevSharingReport(models.Model):
    _name = "tmf.party.rev.sharing.report"
    _description = "TMF737 PartyRevSharingReport"
    _inherit = ["tmf.model.mixin"]

    create_date_time = fields.Char(string="createDate")
    last_update = fields.Char(string="lastUpdate")
    status = fields.Char(string="status")

    party_rev_sharing_model_json = fields.Text(string="partyRevSharingModel")
    cdr_transaction_json = fields.Text(string="cdrTransaction")
    party_rev_sharing_report_item_json = fields.Text(string="partyRevSharingReportItem")
    money_json = fields.Text(string="money")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/revenueSharingReportManagement/v5/partyRevSharingReport"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "partyRevSharingModel": _loads(self.party_rev_sharing_model_json),
            "cdrTransaction": _loads(self.cdr_transaction_json),
            "partyRevSharingReportItem": _loads(self.party_rev_sharing_report_item_json),
            "money": _loads(self.money_json),
            "createDate": self.create_date_time,
            "lastUpdate": self.last_update,
            "status": self.status,
            "@type": self.tmf_type_value or "PartyRevSharingReport",
            "@baseType": self.base_type or "PartyRevSharingReport",
            "@schemaLocation": self.schema_location or "https://tmforum.org/schema",
        }
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("createDate", "create_date_time"),
            ("lastUpdate", "last_update"),
            ("status", "status"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("partyRevSharingModel", "party_rev_sharing_model_json"),
            ("cdrTransaction", "cdr_transaction_json"),
            ("partyRevSharingReportItem", "party_rev_sharing_report_item_json"),
            ("money", "money_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="partyRevSharingReport",
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
                    api_name="partyRevSharingReport",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
