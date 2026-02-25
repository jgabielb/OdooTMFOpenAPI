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


class _TMF714QualificationMixin(models.AbstractModel):
    _name = "tmf.work.qualification.mixin"
    _description = "TMF714 Common Qualification Mixin"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    external_id = fields.Char(string="externalId")
    state = fields.Char(string="state")
    expected_qualification_date = fields.Char(string="expectedQualificationDate")
    effective_qualification_date = fields.Char(string="effectiveQualificationDate")
    estimated_response_date = fields.Char(string="estimatedResponseDate")
    expiration_date = fields.Char(string="expirationDate")
    instant_sync_qualification = fields.Boolean(string="instantSyncQualification")

    place_json = fields.Text(string="place")
    related_party_json = fields.Text(string="relatedParty")
    work_qualification_item_json = fields.Text(string="workQualificationItem")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "externalId": self.external_id,
            "state": self.state,
            "expectedQualificationDate": self.expected_qualification_date,
            "effectiveQualificationDate": self.effective_qualification_date,
            "estimatedResponseDate": self.estimated_response_date,
            "expirationDate": self.expiration_date,
            "instantSyncQualification": self.instant_sync_qualification,
            "place": _loads(self.place_json),
            "relatedParty": _loads(self.related_party_json),
            "workQualificationItem": _loads(self.work_qualification_item_json),
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("externalId", "external_id"),
            ("state", "state"),
            ("expectedQualificationDate", "expected_qualification_date"),
            ("effectiveQualificationDate", "effective_qualification_date"),
            ("estimatedResponseDate", "estimated_response_date"),
            ("expirationDate", "expiration_date"),
            ("instantSyncQualification", "instant_sync_qualification"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("place", "place_json"),
            ("relatedParty", "related_party_json"),
            ("workQualificationItem", "work_qualification_item_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
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


class TMFCheckWorkQualification(models.Model):
    _name = "tmf.check.work.qualification"
    _description = "TMF714 CheckWorkQualification"
    _inherit = ["tmf.work.qualification.mixin"]

    check_work_qualification_date = fields.Char(string="checkWorkQualificationDate")
    qualification_result = fields.Char(string="qualificationResult")
    provide_alternative = fields.Boolean(string="provideAlternative")
    provide_unavailability_reason = fields.Boolean(string="provideUnavailabilityReason")

    def _get_tmf_api_path(self):
        return "/workQualificationManagement/v4/checkWorkQualification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "CheckWorkQualification"
        payload["checkWorkQualificationDate"] = self.check_work_qualification_date
        payload["qualificationResult"] = self.qualification_result
        payload["provideAlternative"] = self.provide_alternative
        payload["provideUnavailabilityReason"] = self.provide_unavailability_reason
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("checkWorkQualificationDate", "check_work_qualification_date"),
            ("qualificationResult", "qualification_result"),
            ("provideAlternative", "provide_alternative"),
            ("provideUnavailabilityReason", "provide_unavailability_reason"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("checkWorkQualification", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("checkWorkQualification", "update", rec)
            if state_changed:
                self._notify("checkWorkQualification", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="checkWorkQualification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFQueryWorkQualification(models.Model):
    _name = "tmf.query.work.qualification"
    _description = "TMF714 QueryWorkQualification"
    _inherit = ["tmf.work.qualification.mixin"]

    query_work_qualification_date = fields.Char(string="queryWorkQualificationDate")
    search_criteria_json = fields.Text(string="searchCriteria")

    def _get_tmf_api_path(self):
        return "/workQualificationManagement/v4/queryWorkQualification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "QueryWorkQualification"
        payload["queryWorkQualificationDate"] = self.query_work_qualification_date
        payload["searchCriteria"] = _loads(self.search_criteria_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        if "queryWorkQualificationDate" in data:
            vals["query_work_qualification_date"] = data.get("queryWorkQualificationDate")
        if "searchCriteria" in data:
            vals["search_criteria_json"] = _dumps(data.get("searchCriteria"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("queryWorkQualification", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("queryWorkQualification", "update", rec)
            if state_changed:
                self._notify("queryWorkQualification", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="queryWorkQualification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

