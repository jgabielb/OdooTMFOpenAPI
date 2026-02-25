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


class _TMF713CommonMixin(models.AbstractModel):
    _name = "tmf.work.common.mixin"
    _description = "TMF713 Common Mixin"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    name = fields.Char(string="name")
    version = fields.Char(string="version")
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
            "name": self.name,
            "version": self.version,
            "state": self.state,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("name", "name"),
            ("version", "version"),
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


class TMFWork(models.Model):
    _name = "tmf.work"
    _description = "TMF713 Work"
    _inherit = ["tmf.work.common.mixin"]

    completion_date = fields.Char(string="completionDate")
    expected_completion_date = fields.Char(string="expectedCompletionDate")
    order_date = fields.Char(string="orderDate")
    percentage_complete = fields.Float(string="percentageComplete")
    work_priority = fields.Char(string="workPriority")
    work_type = fields.Char(string="workType")

    actual_duration_json = fields.Text(string="actualDuration")
    agreement_json = fields.Text(string="agreement")
    appointment_json = fields.Text(string="appointment")
    current_duration_json = fields.Text(string="currentDuration")
    delivery_time_slot_json = fields.Text(string="deliveryTimeSlot")
    note_json = fields.Text(string="note")
    place_json = fields.Text(string="place")
    planned_duration_json = fields.Text(string="plannedDuration")
    quantity_json = fields.Text(string="quantity")
    related_party_json = fields.Text(string="relatedParty")
    scheduled_duration_json = fields.Text(string="scheduledDuration")
    work_json = fields.Text(string="work")
    work_characteristic_json = fields.Text(string="workCharacteristic")
    work_order_item_json = fields.Text(string="workOrderItem")
    work_price_json = fields.Text(string="workPrice")
    work_relationship_json = fields.Text(string="workRelationship")
    work_specification_json = fields.Text(string="workSpecification")
    workforce_employee_assignment_json = fields.Text(string="workforceEmployeeAssignment")

    def _get_tmf_api_path(self):
        return "/workManagement/v4/work"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "Work"
        payload["completionDate"] = self.completion_date
        payload["expectedCompletionDate"] = self.expected_completion_date
        payload["orderDate"] = self.order_date
        payload["percentageComplete"] = self.percentage_complete
        payload["workPriority"] = self.work_priority
        payload["workType"] = self.work_type
        payload["actualDuration"] = _loads(self.actual_duration_json)
        payload["agreement"] = _loads(self.agreement_json)
        payload["appointment"] = _loads(self.appointment_json)
        payload["currentDuration"] = _loads(self.current_duration_json)
        payload["deliveryTimeSlot"] = _loads(self.delivery_time_slot_json)
        payload["note"] = _loads(self.note_json)
        payload["place"] = _loads(self.place_json)
        payload["plannedDuration"] = _loads(self.planned_duration_json)
        payload["quantity"] = _loads(self.quantity_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["scheduledDuration"] = _loads(self.scheduled_duration_json)
        payload["work"] = _loads(self.work_json)
        payload["workCharacteristic"] = _loads(self.work_characteristic_json)
        payload["workOrderItem"] = _loads(self.work_order_item_json)
        payload["workPrice"] = _loads(self.work_price_json)
        payload["workRelationship"] = _loads(self.work_relationship_json)
        payload["workSpecification"] = _loads(self.work_specification_json)
        payload["workforceEmployeeAssignment"] = _loads(self.workforce_employee_assignment_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("completionDate", "completion_date"),
            ("expectedCompletionDate", "expected_completion_date"),
            ("orderDate", "order_date"),
            ("percentageComplete", "percentage_complete"),
            ("workPriority", "work_priority"),
            ("workType", "work_type"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("actualDuration", "actual_duration_json"),
            ("agreement", "agreement_json"),
            ("appointment", "appointment_json"),
            ("currentDuration", "current_duration_json"),
            ("deliveryTimeSlot", "delivery_time_slot_json"),
            ("note", "note_json"),
            ("place", "place_json"),
            ("plannedDuration", "planned_duration_json"),
            ("quantity", "quantity_json"),
            ("relatedParty", "related_party_json"),
            ("scheduledDuration", "scheduled_duration_json"),
            ("work", "work_json"),
            ("workCharacteristic", "work_characteristic_json"),
            ("workOrderItem", "work_order_item_json"),
            ("workPrice", "work_price_json"),
            ("workRelationship", "work_relationship_json"),
            ("workSpecification", "work_specification_json"),
            ("workforceEmployeeAssignment", "workforce_employee_assignment_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("work", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("work", "update", rec)
            if state_changed:
                self._notify("work", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="work",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFWorkSpecification(models.Model):
    _name = "tmf.work.specification"
    _description = "TMF713 WorkSpecification"
    _inherit = ["tmf.work.common.mixin"]

    lifecycle_status = fields.Char(string="lifecycleStatus")
    is_bundle = fields.Boolean(string="isBundle")
    is_appointment_required = fields.Boolean(string="isAppointmentRequired")
    last_update = fields.Char(string="lastUpdate")

    attachment_json = fields.Text(string="attachment")
    constraint_json = fields.Text(string="constraint")
    entity_spec_relationship_json = fields.Text(string="entitySpecRelationship")
    related_party_json = fields.Text(string="relatedParty")
    spec_characteristic_json = fields.Text(string="specCharacteristic")
    target_entity_schema_json = fields.Text(string="targetEntitySchema")
    valid_for_json = fields.Text(string="validFor")
    work_spec_relationship_json = fields.Text(string="workSpecRelationship")

    def _get_tmf_api_path(self):
        return "/workManagement/v4/workSpecification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "WorkSpecification"
        payload["lifecycleStatus"] = self.lifecycle_status
        payload["isBundle"] = self.is_bundle
        payload["isAppointmentRequired"] = self.is_appointment_required
        payload["lastUpdate"] = self.last_update
        payload["attachment"] = _loads(self.attachment_json)
        payload["constraint"] = _loads(self.constraint_json)
        payload["entitySpecRelationship"] = _loads(self.entity_spec_relationship_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["specCharacteristic"] = _loads(self.spec_characteristic_json)
        payload["targetEntitySchema"] = _loads(self.target_entity_schema_json)
        payload["validFor"] = _loads(self.valid_for_json)
        payload["workSpecRelationship"] = _loads(self.work_spec_relationship_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("lifecycleStatus", "lifecycle_status"),
            ("isBundle", "is_bundle"),
            ("isAppointmentRequired", "is_appointment_required"),
            ("lastUpdate", "last_update"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("attachment", "attachment_json"),
            ("constraint", "constraint_json"),
            ("entitySpecRelationship", "entity_spec_relationship_json"),
            ("relatedParty", "related_party_json"),
            ("specCharacteristic", "spec_characteristic_json"),
            ("targetEntitySchema", "target_entity_schema_json"),
            ("validFor", "valid_for_json"),
            ("workSpecRelationship", "work_spec_relationship_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("workSpecification", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("workSpecification", "update", rec)
            if state_changed:
                self._notify("workSpecification", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="workSpecification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

