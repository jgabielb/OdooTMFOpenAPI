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


class _TMF724CommonMixin(models.AbstractModel):
    _name = "tmf.incident.common.mixin"
    _description = "TMF724 Common Incident Mixin"
    _inherit = ["tmf.model.mixin"]

    state = fields.Char(string="state")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "state": self.state,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
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


class TMFIncident(models.Model):
    _name = "tmf.incident"
    _description = "TMF724 Incident"
    _inherit = ["tmf.incident.common.mixin"]

    name = fields.Char(string="name")
    category = fields.Char(string="category")
    priority = fields.Char(string="priority")
    ack_state = fields.Char(string="ackState")
    domain = fields.Char(string="domain")
    occur_time = fields.Char(string="occurTime")
    ack_time = fields.Char(string="ackTime")
    clear_time = fields.Char(string="clearTime")
    update_time = fields.Char(string="updateTime")
    incident_detail = fields.Char(string="incidentDetail")
    incident_resolution_suggestion = fields.Char(string="incidentResolutionSuggestion")
    external_identifier = fields.Char(string="externalIdentifier")
    severity = fields.Char(string="severity")
    urgency = fields.Char(string="urgency")
    source_object_json = fields.Text(string="sourceObject")
    affected_entity_json = fields.Text(string="affectedEntity")
    event_id_json = fields.Text(string="eventId")
    extension_info_json = fields.Text(string="extensionInfo")
    related_party_json = fields.Text(string="relatedParty")
    related_entity_json = fields.Text(string="relatedEntity")
    root_cause_json = fields.Text(string="rootCause")
    note_json = fields.Text(string="note")

    def _get_tmf_api_path(self):
        return "/Incident/v4/incident"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "name": self.name,
                "category": self.category,
                "priority": self.priority,
                "ackState": self.ack_state,
                "domain": self.domain,
                "occurTime": self.occur_time,
                "ackTime": self.ack_time,
                "clearTime": self.clear_time,
                "updateTime": self.update_time,
                "incidentDetail": self.incident_detail,
                "incidentResolutionSuggestion": self.incident_resolution_suggestion,
                "externalIdentifier": self.external_identifier,
                "severity": self.severity,
                "urgency": self.urgency,
                "sourceObject": _loads(self.source_object_json),
                "affectedEntity": _loads(self.affected_entity_json),
                "eventId": _loads(self.event_id_json),
                "extensionInfo": _loads(self.extension_info_json),
                "relatedParty": _loads(self.related_party_json),
                "relatedEntity": _loads(self.related_entity_json),
                "rootCause": _loads(self.root_cause_json),
                "note": _loads(self.note_json),
                "@type": self.tmf_type_value or "Incident",
            }
        )
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("name", "name"),
            ("category", "category"),
            ("priority", "priority"),
            ("ackState", "ack_state"),
            ("domain", "domain"),
            ("occurTime", "occur_time"),
            ("ackTime", "ack_time"),
            ("clearTime", "clear_time"),
            ("updateTime", "update_time"),
            ("incidentDetail", "incident_detail"),
            ("incidentResolutionSuggestion", "incident_resolution_suggestion"),
            ("externalIdentifier", "external_identifier"),
            ("severity", "severity"),
            ("urgency", "urgency"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("sourceObject", "source_object_json"),
            ("affectedEntity", "affected_entity_json"),
            ("eventId", "event_id_json"),
            ("extensionInfo", "extension_info_json"),
            ("relatedParty", "related_party_json"),
            ("relatedEntity", "related_entity_json"),
            ("rootCause", "root_cause_json"),
            ("note", "note_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("incident", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("incident", "update", rec)
            if state_changed:
                self._notify("incident", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="incident",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFDiagnoseIncident(models.Model):
    _name = "tmf.diagnose.incident"
    _description = "TMF724 DiagnoseIncident"
    _inherit = ["tmf.incident.common.mixin"]

    error_log = fields.Char(string="errorLog")
    incident_json = fields.Text(string="incident")

    def _get_tmf_api_path(self):
        return "/Incident/v4/diagnoseIncident"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "errorLog": self.error_log,
                "incident": _loads(self.incident_json),
                "@type": self.tmf_type_value or "DiagnoseIncident",
            }
        )
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        if "errorLog" in data:
            vals["error_log"] = data.get("errorLog")
        if "incident" in data:
            vals["incident_json"] = _dumps(data.get("incident"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("diagnoseIncident", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("diagnoseIncident", "update", rec)
            if state_changed:
                self._notify("diagnoseIncident", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="diagnoseIncident",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFResolveIncident(models.Model):
    _name = "tmf.resolve.incident"
    _description = "TMF724 ResolveIncident"
    _inherit = ["tmf.incident.common.mixin"]

    error_log = fields.Char(string="errorLog")
    clear_time = fields.Char(string="clearTime")
    incident_json = fields.Text(string="incident")

    def _get_tmf_api_path(self):
        return "/Incident/v4/resolveIncident"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "errorLog": self.error_log,
                "clearTime": self.clear_time,
                "incident": _loads(self.incident_json),
                "@type": self.tmf_type_value or "ResolveIncident",
            }
        )
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        if "errorLog" in data:
            vals["error_log"] = data.get("errorLog")
        if "clearTime" in data:
            vals["clear_time"] = data.get("clearTime")
        if "incident" in data:
            vals["incident_json"] = _dumps(data.get("incident"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("resolveIncident", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("resolveIncident", "update", rec)
            if state_changed:
                self._notify("resolveIncident", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="resolveIncident",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
