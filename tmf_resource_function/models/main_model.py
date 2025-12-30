from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.resource.function'
    _description = 'ResourceFunction'
    _inherit = ['tmf.model.mixin']

    category = fields.Char(string="category", help="Category of the concrete resource. e.g Gold, Silver for MSISDN concrete resource")
    description = fields.Char(string="description", help="free-text description of the resource")
    end_operating_date = fields.Datetime(string="endOperatingDate", help="A date time( DateTime). The date till the resource is operating")
    function_type = fields.Char(string="functionType", help="A type of the Resource Function as specified by the provider of the API.")
    name = fields.Char(string="name", help="A string used to give a name to the resource")
    priority = fields.Integer(string="priority", help="Priority of the Resource Function. Decides what happens in a contention scenario.")
    resource_version = fields.Char(string="resourceVersion", help="A field that identifies the specific version of an instance of a resource.")
    role = fields.Char(string="role", help="Role of the Resource Function. Used when Resource Function is a component of a composite Resource Fu")
    start_operating_date = fields.Datetime(string="startOperatingDate", help="A date time( DateTime). The date from which the resource is operating")
    value = fields.Char(string="value", help="the value of the logical resource. E.g '0746712345' for  MSISDN's")
    activation_feature = fields.Char(string="activationFeature", help="Configuration features")
    administrative_state = fields.Char(string="administrativeState", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    attachment = fields.Char(string="attachment", help="")
    auto_modification = fields.Char(string="autoModification", help="List of the kinds of auto-modifications that are applied to a given network service e.g what can be ")
    connection_point = fields.Char(string="connectionPoint", help="External connection points of the resource function. These are the service access points (SAP) where")
    connectivity = fields.Char(string="connectivity", help="Internal connectivity of contained resource functions.")
    note = fields.Char(string="note", help="")
    operational_state = fields.Char(string="operationalState", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    place = fields.Char(string="place", help="")
    related_party = fields.Char(string="relatedParty", help="")
    resource_characteristic = fields.Char(string="resourceCharacteristic", help="")
    resource_relationship = fields.Char(string="resourceRelationship", help="")
    resource_specification = fields.Char(string="resourceSpecification", help="")
    resource_status = fields.Char(string="resourceStatus", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    schedule = fields.Char(string="schedule", help="This is a reference to a schedule. Allows consumers to schedule modifications to the service at cert")
    usage_state = fields.Char(string="usageState", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")

    def _get_tmf_api_path(self):
        return "/resource_functionManagement/v4/ResourceFunction"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ResourceFunction",
            "category": self.category,
            "description": self.description,
            "endOperatingDate": self.end_operating_date.isoformat() if self.end_operating_date else None,
            "functionType": self.function_type,
            "name": self.name,
            "priority": self.priority,
            "resourceVersion": self.resource_version,
            "role": self.role,
            "startOperatingDate": self.start_operating_date.isoformat() if self.start_operating_date else None,
            "value": self.value,
            "activationFeature": self.activation_feature,
            "administrativeState": self.administrative_state,
            "attachment": self.attachment,
            "autoModification": self.auto_modification,
            "connectionPoint": self.connection_point,
            "connectivity": self.connectivity,
            "note": self.note,
            "operationalState": self.operational_state,
            "place": self.place,
            "relatedParty": self.related_party,
            "resourceCharacteristic": self.resource_characteristic,
            "resourceRelationship": self.resource_relationship,
            "resourceSpecification": self.resource_specification,
            "resourceStatus": self.resource_status,
            "schedule": self.schedule,
            "usageState": self.usage_state,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('resourceFunction', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('resourceFunction', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='resourceFunction',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
