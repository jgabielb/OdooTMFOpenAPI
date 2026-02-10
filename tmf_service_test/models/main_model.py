from odoo import models, fields, api
import json

def _json_dumps(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else False

def _json_loads(v):
    if not v:
        return None
    if isinstance(v, (dict, list)):
        return v
    return json.loads(v)

class TMFServiceTest(models.Model):
    _name = "tmf.service.test"
    _description = "ServiceTest"
    _inherit = ["tmf.model.mixin"]

    # Scalars
    name = fields.Char(required=True)
    description = fields.Char()
    mode = fields.Char()   # PROACTIVE | ONDEMAND
    state = fields.Char()  # acknowledged, rejected, pending, inProgress, cancelled, completed, failed, ...

    start_date_time = fields.Datetime(string="startDateTime")
    end_date_time = fields.Datetime(string="endDateTime")

    # JSON complex
    characteristic_json = fields.Text(string="characteristic")
    related_party_json = fields.Text(string="relatedParty")
    related_service_json = fields.Text(string="relatedService", required=True)
    test_specification_json = fields.Text(string="testSpecification", required=True)
    test_measure_json = fields.Text(string="testMeasure")
    valid_for_json = fields.Text(string="validFor")

    # Meta
    at_type = fields.Char(string="@type", default="ServiceTest")
    at_base_type = fields.Char(string="@baseType")
    at_schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/serviceTestManagement/v4/serviceTest"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {"id": self.tmf_id, "href": self.href, "@type": self.at_type or "ServiceTest"}
        if self.at_base_type:
            payload["@baseType"] = self.at_base_type
        if self.at_schema_location:
            payload["@schemaLocation"] = self.at_schema_location

        if self.name:
            payload["name"] = self.name
        if self.description:
            payload["description"] = self.description
        if self.mode:
            payload["mode"] = self.mode
        if self.state:
            payload["state"] = self.state
        if self.start_date_time:
            payload["startDateTime"] = self.start_date_time.isoformat()
        if self.end_date_time:
            payload["endDateTime"] = self.end_date_time.isoformat()

        if self.characteristic_json:
            payload["characteristic"] = _json_loads(self.characteristic_json)
        if self.related_party_json:
            payload["relatedParty"] = _json_loads(self.related_party_json)
        if self.related_service_json:
            payload["relatedService"] = _json_loads(self.related_service_json)
        if self.test_specification_json:
            payload["testSpecification"] = _json_loads(self.test_specification_json)
        if self.test_measure_json:
            payload["testMeasure"] = _json_loads(self.test_measure_json)
        if self.valid_for_json:
            payload["validFor"] = _json_loads(self.valid_for_json)

        return payload

    @api.model
    def create_from_tmf(self, data: dict, base_url: str):
        if not data.get("name") or not data.get("relatedService") or not data.get("testSpecification"):
            raise ValueError("name, relatedService, testSpecification are mandatory")

        vals = {
            "name": data.get("name"),
            "description": data.get("description"),
            "mode": data.get("mode"),
            "state": data.get("state"),
            "at_type": data.get("@type") or "ServiceTest",
            "at_base_type": data.get("@baseType"),
            "at_schema_location": data.get("@schemaLocation"),
            "related_service_json": _json_dumps(data.get("relatedService")),
            "test_specification_json": _json_dumps(data.get("testSpecification")),
        }

        if "characteristic" in data:
            vals["characteristic_json"] = _json_dumps(data.get("characteristic"))
        if "relatedParty" in data:
            vals["related_party_json"] = _json_dumps(data.get("relatedParty"))
        if "testMeasure" in data:
            vals["test_measure_json"] = _json_dumps(data.get("testMeasure"))
        if "validFor" in data:
            vals["valid_for_json"] = _json_dumps(data.get("validFor"))

        if data.get("startDateTime"):
            vals["start_date_time"] = data.get("startDateTime")
        if data.get("endDateTime"):
            vals["end_date_time"] = data.get("endDateTime")

        rec = self.sudo().create(vals)
        # Ensure href matches CTK expected pattern: http://localhost:8069/tmf-api/.../id
        rec.href = f"{base_url}{'/tmf-api'}{rec._get_tmf_api_path()}/{rec.tmf_id}"
        return rec

    def write_from_tmf(self, patch: dict):
        # Patchable fields per spec (ServiceTest): characteristic, description, endDateTime, mode, name,
        # relatedParty, relatedService, startDateTime, state, testMeasure, testSpecification, validFor
        vals = {}
        if "name" in patch:
            vals["name"] = patch["name"]
        if "description" in patch:
            vals["description"] = patch["description"]
        if "mode" in patch:
            vals["mode"] = patch["mode"]
        if "state" in patch:
            vals["state"] = patch["state"]
        if "startDateTime" in patch:
            vals["start_date_time"] = patch["startDateTime"]
        if "endDateTime" in patch:
            vals["end_date_time"] = patch["endDateTime"]

        if "characteristic" in patch:
            vals["characteristic_json"] = _json_dumps(patch["characteristic"])
        if "relatedParty" in patch:
            vals["related_party_json"] = _json_dumps(patch["relatedParty"])
        if "relatedService" in patch:
            vals["related_service_json"] = _json_dumps(patch["relatedService"])
        if "testSpecification" in patch:
            vals["test_specification_json"] = _json_dumps(patch["testSpecification"])
        if "testMeasure" in patch:
            vals["test_measure_json"] = _json_dumps(patch["testMeasure"])
        if "validFor" in patch:
            vals["valid_for_json"] = _json_dumps(patch["validFor"])

        return self.sudo().write(vals)

    # Notifications (reuse your hub mechanism if present)
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify("serviceTest", "create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._notify("serviceTest", "update")
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="serviceTest", event_type="delete", resource_json=resource
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, event_type):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name, event_type=event_type, resource_json=self.to_tmf_json()
            )
        except Exception:
            pass


class TMFServiceTestSpecification(models.Model):
    _name = "tmf.service.test.specification"
    _description = "ServiceTestSpecification"
    _inherit = ["tmf.model.mixin"]

    # Scalars
    name = fields.Char(required=True)
    description = fields.Char()
    is_bundle = fields.Boolean(string="isBundle")
    last_update = fields.Datetime(string="lastUpdate")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    version = fields.Char()

    # Complex JSON (store as Text)
    related_service_spec_json = fields.Text(string="relatedServiceSpecification", required=True)  # list[*]
    service_test_spec_rel_json = fields.Text(string="serviceTestSpecRelationship")              # list[*]
    test_measure_def_json = fields.Text(string="testMeasureDefinition")                         # list[*]
    attachment_json = fields.Text(string="attachment")                                          # list[*]
    constraint_json = fields.Text(string="constraint")                                          # list[*]
    entity_spec_rel_json = fields.Text(string="entitySpecRelationship")                         # list[*]
    related_party_json = fields.Text(string="relatedParty")                                     # list[*]
    spec_characteristic_json = fields.Text(string="specCharacteristic")                         # list[*]
    target_entity_schema_json = fields.Text(string="targetEntitySchema")                        # object
    valid_for_json = fields.Text(string="validFor")                                             # object

    # Meta
    at_type = fields.Char(string="@type", default="ServiceTestSpecification")
    at_base_type = fields.Char(string="@baseType")
    at_schema_location = fields.Char(string="@schemaLocation")

    def _get_tmf_api_path(self):
        return "/serviceTestManagement/v4/serviceTestSpecification"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {"id": self.tmf_id, "href": self.href, "@type": self.at_type or "ServiceTestSpecification"}

        if self.at_base_type:
            payload["@baseType"] = self.at_base_type
        if self.at_schema_location:
            payload["@schemaLocation"] = self.at_schema_location

        # Scalars
        if self.name:
            payload["name"] = self.name
        if self.description:
            payload["description"] = self.description
        payload["isBundle"] = bool(self.is_bundle)
        if self.last_update:
            payload["lastUpdate"] = self.last_update.isoformat()
        if self.lifecycle_status:
            payload["lifecycleStatus"] = self.lifecycle_status
        if self.version:
            payload["version"] = self.version

        # Complex
        if self.related_service_spec_json:
            payload["relatedServiceSpecification"] = _json_loads(self.related_service_spec_json)
        if self.service_test_spec_rel_json:
            payload["serviceTestSpecRelationship"] = _json_loads(self.service_test_spec_rel_json)
        if self.test_measure_def_json:
            payload["testMeasureDefinition"] = _json_loads(self.test_measure_def_json)
        if self.attachment_json:
            payload["attachment"] = _json_loads(self.attachment_json)
        if self.constraint_json:
            payload["constraint"] = _json_loads(self.constraint_json)
        if self.entity_spec_rel_json:
            payload["entitySpecRelationship"] = _json_loads(self.entity_spec_rel_json)
        if self.related_party_json:
            payload["relatedParty"] = _json_loads(self.related_party_json)
        if self.spec_characteristic_json:
            payload["specCharacteristic"] = _json_loads(self.spec_characteristic_json)
        if self.target_entity_schema_json:
            payload["targetEntitySchema"] = _json_loads(self.target_entity_schema_json)
        if self.valid_for_json:
            payload["validFor"] = _json_loads(self.valid_for_json)

        return payload

    @api.model
    def create_from_tmf(self, data: dict, base_url: str):
        # Mandatory attributes per TMF653: name, relatedServiceSpecification
        if not data.get("name") or not data.get("relatedServiceSpecification"):
            raise ValueError("name, relatedServiceSpecification are mandatory")

        vals = {
            "name": data.get("name"),
            "description": data.get("description"),
            "is_bundle": bool(data.get("isBundle")) if "isBundle" in data else False,
            "lifecycle_status": data.get("lifecycleStatus"),
            "version": data.get("version"),
            "at_type": data.get("@type") or "ServiceTestSpecification",
            "at_base_type": data.get("@baseType"),
            "at_schema_location": data.get("@schemaLocation"),
            "related_service_spec_json": _json_dumps(data.get("relatedServiceSpecification")),
        }

        if data.get("lastUpdate"):
            vals["last_update"] = data.get("lastUpdate")

        # Optional complex structures
        for src_key, dst in [
            ("serviceTestSpecRelationship", "service_test_spec_rel_json"),
            ("testMeasureDefinition", "test_measure_def_json"),
            ("attachment", "attachment_json"),
            ("constraint", "constraint_json"),
            ("entitySpecRelationship", "entity_spec_rel_json"),
            ("relatedParty", "related_party_json"),
            ("specCharacteristic", "spec_characteristic_json"),
            ("targetEntitySchema", "target_entity_schema_json"),
            ("validFor", "valid_for_json"),
        ]:
            if src_key in data:
                vals[dst] = _json_dumps(data.get(src_key))

        rec = self.sudo().create(vals)
        rec.href = f"{base_url}{'/tmf-api'}{rec._get_tmf_api_path()}/{rec.tmf_id}"
        return rec

    def write_from_tmf(self, patch: dict):
        # Patchable per TMF653: description,isBundle,lastUpdate,lifecycleStatus,name,version,
        # relatedServiceSpecification, serviceTestSpecRelationship, testMeasureDefinition, attachment, constraint,
        # entitySpecRelationship, relatedParty, specCharacteristic, targetEntitySchema
        # Non-patchable: href, id, validFor, @type, @schemaLocation, @baseType
        vals = {}
        if "name" in patch:
            vals["name"] = patch["name"]
        if "description" in patch:
            vals["description"] = patch["description"]
        if "isBundle" in patch:
            vals["is_bundle"] = bool(patch["isBundle"])
        if "lastUpdate" in patch:
            vals["last_update"] = patch["lastUpdate"]
        if "lifecycleStatus" in patch:
            vals["lifecycle_status"] = patch["lifecycleStatus"]
        if "version" in patch:
            vals["version"] = patch["version"]
        if "relatedServiceSpecification" in patch:
            vals["related_service_spec_json"] = _json_dumps(patch["relatedServiceSpecification"])

        for src_key, dst in [
            ("serviceTestSpecRelationship", "service_test_spec_rel_json"),
            ("testMeasureDefinition", "test_measure_def_json"),
            ("attachment", "attachment_json"),
            ("constraint", "constraint_json"),
            ("entitySpecRelationship", "entity_spec_rel_json"),
            ("relatedParty", "related_party_json"),
            ("specCharacteristic", "spec_characteristic_json"),
            ("targetEntitySchema", "target_entity_schema_json"),
        ]:
            if src_key in patch:
                vals[dst] = _json_dumps(patch.get(src_key))

        return self.sudo().write(vals)

    # Notifications
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify("serviceTestSpecification", "create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._notify("serviceTestSpecification", "update")
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="serviceTestSpecification", event_type="delete", resource_json=resource
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, event_type):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name, event_type=event_type, resource_json=self.to_tmf_json()
            )
        except Exception:
            pass
