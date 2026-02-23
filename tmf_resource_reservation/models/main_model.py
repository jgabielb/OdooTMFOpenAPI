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
    return {k: v for k, v in payload.items() if v is not None}


class _TMF716CommonMixin(models.AbstractModel):
    _name = "tmf.resource.reservation.common.mixin"
    _description = "TMF716 Common Mixin"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    state = fields.Char(string="state")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "state": self.state,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("state", "state"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _notify(self, api_name, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass


class TMFResourceReservation(models.Model):
    _name = "tmf.resource.reservation"
    _description = "TMF716 ResourceReservation"
    _inherit = ["tmf.resource.reservation.common.mixin"]

    cancellation_date = fields.Char(string="cancellationDate")
    cancellation_reason = fields.Char(string="cancellationReason")
    completion_date = fields.Char(string="completionDate")
    creation_date = fields.Char(string="creationDate")
    expected_completion_date = fields.Char(string="expectedCompletionDate")
    requested_completion_date = fields.Char(string="requestedCompletionDate")
    requested_start_date = fields.Char(string="requestedStartDate")
    state_change_date = fields.Char(string="stateChangeDate")
    state_change_reason = fields.Char(string="stateChangeReason")

    channel_json = fields.Text(string="channel")
    related_entity_json = fields.Text(string="relatedEntity")
    related_party_json = fields.Text(string="relatedParty")
    reservation_item_json = fields.Text(string="reservationItem")
    reservation_period_json = fields.Text(string="reservationPeriod")
    valid_for_json = fields.Text(string="validFor")

    def _get_tmf_api_path(self):
        return "/resourceReservation/v4/resourceReservation"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "ResourceReservation"
        payload["cancellationDate"] = self.cancellation_date
        payload["cancellationReason"] = self.cancellation_reason
        payload["completionDate"] = self.completion_date
        payload["creationDate"] = self.creation_date
        payload["expectedCompletionDate"] = self.expected_completion_date
        payload["requestedCompletionDate"] = self.requested_completion_date
        payload["requestedStartDate"] = self.requested_start_date
        payload["stateChangeDate"] = self.state_change_date
        payload["stateChangeReason"] = self.state_change_reason
        payload["channel"] = _loads(self.channel_json)
        payload["relatedEntity"] = _loads(self.related_entity_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["reservationItem"] = _loads(self.reservation_item_json)
        payload["reservationPeriod"] = _loads(self.reservation_period_json)
        payload["validFor"] = _loads(self.valid_for_json)
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("cancellationDate", "cancellation_date"),
            ("cancellationReason", "cancellation_reason"),
            ("completionDate", "completion_date"),
            ("creationDate", "creation_date"),
            ("expectedCompletionDate", "expected_completion_date"),
            ("requestedCompletionDate", "requested_completion_date"),
            ("requestedStartDate", "requested_start_date"),
            ("stateChangeDate", "state_change_date"),
            ("stateChangeReason", "state_change_reason"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("channel", "channel_json"),
            ("relatedEntity", "related_entity_json"),
            ("relatedParty", "related_party_json"),
            ("reservationItem", "reservation_item_json"),
            ("reservationPeriod", "reservation_period_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("resourceReservation", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("resourceReservation", "update", rec)
            if state_changed:
                self._notify("resourceReservation", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="resourceReservation",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFCancelResourceReservation(models.Model):
    _name = "tmf.cancel.resource.reservation"
    _description = "TMF716 CancelResourceReservation"
    _inherit = ["tmf.resource.reservation.common.mixin"]

    cancellation_reason = fields.Char(string="cancellationReason")
    requested_cancellation_date = fields.Char(string="requestedCancellationDate")
    effective_cancellation_date = fields.Char(string="effectiveCancellationDate")
    resource_reservation_json = fields.Text(string="resourceReservation")

    def _get_tmf_api_path(self):
        return "/resourceReservation/v4/cancelResourceReservation"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "CancelResourceReservation"
        payload["cancellationReason"] = self.cancellation_reason
        payload["requestedCancellationDate"] = self.requested_cancellation_date
        payload["effectiveCancellationDate"] = self.effective_cancellation_date
        payload["resourceReservation"] = _loads(self.resource_reservation_json)
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("cancellationReason", "cancellation_reason"),
            ("requestedCancellationDate", "requested_cancellation_date"),
            ("effectiveCancellationDate", "effective_cancellation_date"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if "resourceReservation" in data:
            vals["resource_reservation_json"] = _dumps(data.get("resourceReservation"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("cancelResourceReservation", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("cancelResourceReservation", "update", rec)
            if state_changed:
                self._notify("cancelResourceReservation", "state_change", rec)
        return res
