from odoo import models, fields, api
import json

API_BASE = "/tmf-api/resourceFunctionActivation/v4"
RESOURCE = "resourceFunction"
BASE_PATH = f"{API_BASE}/{RESOURCE}"

def _dumps(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else False

def _loads(v):
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None

class TMFResourceFunction(models.Model):
    _name = "tmf.resource.function"
    _description = "ResourceFunction"
    _inherit = ["tmf.model.mixin"]

    # Simple scalar fields
    category = fields.Char(string="category")
    description = fields.Char(string="description")
    end_operating_date = fields.Datetime(string="endOperatingDate")
    function_type = fields.Char(string="functionType")
    name = fields.Char(string="name")
    priority = fields.Integer(string="priority")
    resource_version = fields.Char(string="resourceVersion")
    role = fields.Char(string="role")
    start_operating_date = fields.Datetime(string="startOperatingDate")
    value = fields.Char(string="value")

    administrative_state = fields.Char(string="administrativeState")
    operational_state = fields.Char(string="operationalState")
    resource_status = fields.Char(string="resourceStatus")

    # usageState exists in resource model, but is NON-PATCHABLE; typically managed by system
    usage_state = fields.Char(string="usageState")

    # Complex TMF fields -> JSON text
    resource_specification_json = fields.Text(string="resourceSpecification")     # object
    resource_characteristic_json = fields.Text(string="resourceCharacteristic")   # array
    activation_feature_json = fields.Text(string="activationFeature")             # array
    attachment_json = fields.Text(string="attachment")                            # array
    note_json = fields.Text(string="note")                                        # array
    related_party_json = fields.Text(string="relatedParty")                       # array
    place_json = fields.Text(string="place")                                      # object
    resource_relationship_json = fields.Text(string="resourceRelationship")       # array
    connection_point_json = fields.Text(string="connectionPoint")                 # array
    connectivity_json = fields.Text(string="connectivity")                        # array
    schedule_json = fields.Text(string="schedule")                                # array
    auto_modification_json = fields.Text(string="autoModification")               # array

    def _get_tmf_api_path(self):
        # TMF664 base path
        return BASE_PATH

    def to_tmf_json(self):
        self.ensure_one()
        rid = self.tmf_id
        href = f"{BASE_PATH}/{rid}" if rid else None

        return {
            "id": rid,
            "href": href,
            "@type": "ResourceFunction",
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "value": self.value,
            "priority": self.priority,
            "role": self.role,
            "functionType": self.function_type,
            "resourceVersion": self.resource_version,
            "startOperatingDate": self.start_operating_date.isoformat() if self.start_operating_date else None,
            "endOperatingDate": self.end_operating_date.isoformat() if self.end_operating_date else None,
            "administrativeState": self.administrative_state,
            "operationalState": self.operational_state,
            "resourceStatus": self.resource_status,
            "usageState": self.usage_state,

            "resourceSpecification": _loads(self.resource_specification_json),
            "resourceCharacteristic": _loads(self.resource_characteristic_json),
            "activationFeature": _loads(self.activation_feature_json),
            "attachment": _loads(self.attachment_json),
            "note": _loads(self.note_json),
            "relatedParty": _loads(self.related_party_json),
            "place": _loads(self.place_json),
            "resourceRelationship": _loads(self.resource_relationship_json),
            "connectionPoint": _loads(self.connection_point_json),
            "connectivity": _loads(self.connectivity_json),
            "schedule": _loads(self.schedule_json),
            "autoModification": _loads(self.auto_modification_json),
        }

    def from_tmf_json(self, data, partial=False):
        """
        Map TMF664 JSON -> Odoo create/write vals.
        - Enforces that resourceSpecification is stored as JSON.
        - Does NOT allow client to set id/href here (controller blocks).
        """
        vals = {}

        # simple scalars
        for k, field_name in [
            ("category", "category"),
            ("description", "description"),
            ("functionType", "function_type"),
            ("name", "name"),
            ("priority", "priority"),
            ("resourceVersion", "resource_version"),
            ("role", "role"),
            ("value", "value"),
            ("administrativeState", "administrative_state"),
            ("operationalState", "operational_state"),
            ("resourceStatus", "resource_status"),
        ]:
            if k in data:
                vals[field_name] = data.get(k)

        # datetimes as-is; adapt if your other modules already normalize TZ
        if "startOperatingDate" in data:
            vals["start_operating_date"] = data.get("startOperatingDate")
        if "endOperatingDate" in data:
            vals["end_operating_date"] = data.get("endOperatingDate")

        # complex structures
        if "resourceSpecification" in data:
            vals["resource_specification_json"] = _dumps(data.get("resourceSpecification"))
        if "resourceCharacteristic" in data:
            vals["resource_characteristic_json"] = _dumps(data.get("resourceCharacteristic"))
        if "activationFeature" in data:
            vals["activation_feature_json"] = _dumps(data.get("activationFeature"))
        if "attachment" in data:
            vals["attachment_json"] = _dumps(data.get("attachment"))
        if "note" in data:
            vals["note_json"] = _dumps(data.get("note"))
        if "relatedParty" in data:
            vals["related_party_json"] = _dumps(data.get("relatedParty"))
        if "place" in data:
            vals["place_json"] = _dumps(data.get("place"))
        if "resourceRelationship" in data:
            vals["resource_relationship_json"] = _dumps(data.get("resourceRelationship"))
        if "connectionPoint" in data:
            vals["connection_point_json"] = _dumps(data.get("connectionPoint"))
        if "connectivity" in data:
            vals["connectivity_json"] = _dumps(data.get("connectivity"))
        if "schedule" in data:
            vals["schedule_json"] = _dumps(data.get("schedule"))
        if "autoModification" in data:
            vals["auto_modification_json"] = _dumps(data.get("autoModification"))

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("resourceFunction", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("resourceFunction", "update", rec)
        return res
