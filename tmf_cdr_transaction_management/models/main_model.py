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
    # Odoo char fields can be False; schema expects strings when present.
    return {k: v for k, v in payload.items() if v is not None and v is not False}


class TMFCdrTransaction(models.Model):
    _name = "tmf.cdr.transaction"
    _description = "TMF735 CdrTransaction"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    requested_initial_state = fields.Char(string="requestedInitialState")
    state = fields.Char(string="state")
    cancellation_date = fields.Char(string="cancellationDate")
    cancellation_reason = fields.Char(string="cancellationReason")
    creation_date = fields.Char(string="creationDate")
    completion_date = fields.Char(string="completionDate")

    related_party_json = fields.Text(string="relatedParty")
    channel_json = fields.Text(string="channel")
    note_json = fields.Text(string="note")
    transaction_item_json = fields.Text(string="transactionItem")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _get_tmf_api_path(self):
        return "/cdrTransactionManagement/v5/cdrTransaction"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "requestedInitialState": self.requested_initial_state,
            "state": self.state,
            "cancellationDate": self.cancellation_date,
            "cancellationReason": self.cancellation_reason,
            "creationDate": self.creation_date,
            "completionDate": self.completion_date,
            "relatedParty": _loads(self.related_party_json),
            "channel": _loads(self.channel_json),
            "note": _loads(self.note_json),
            "transactionItem": _loads(self.transaction_item_json),
            "@type": self.tmf_type_value or "CdrTransaction",
            "@baseType": self.base_type or "CdrTransaction",
            "@schemaLocation": self.schema_location or "https://tmforum.org/schema",
        }
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("requestedInitialState", "requested_initial_state"),
            ("state", "state"),
            ("cancellationDate", "cancellation_date"),
            ("cancellationReason", "cancellation_reason"),
            ("creationDate", "creation_date"),
            ("completionDate", "completion_date"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("relatedParty", "related_party_json"),
            ("channel", "channel_json"),
            ("note", "note_json"),
            ("transactionItem", "transaction_item_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="cdrTransaction",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("creation_date", vals.get("creation_date") or self._now_iso())
            vals.setdefault("state", vals.get("state") or vals.get("requested_initial_state") or "created")
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
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
                    api_name="cdrTransaction",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
