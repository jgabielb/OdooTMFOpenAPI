from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.device'
    _description = 'Device'
    _inherit = ['tmf.model.mixin']

    alternate_name = fields.Char(string="alternateName", help="")
    area_served = fields.Char(string="areaServed", help="")
    battery_level = fields.Float(string="batteryLevel", help="")
    category = fields.Char(string="category", help="Category of the concrete resource. e.g Gold, Silver for MSISDN concrete resource")
    data_provider = fields.Char(string="dataProvider", help="")
    date_created = fields.Datetime(string="dateCreated", help="")
    date_first_used = fields.Datetime(string="dateFirstUsed", help="")
    date_installed = fields.Datetime(string="dateInstalled", help="")
    date_last_calibration = fields.Datetime(string="dateLastCalibration", help="")
    date_last_value_reported = fields.Datetime(string="dateLastValueReported", help="")
    date_manufactured = fields.Datetime(string="dateManufactured", help="")
    date_modified = fields.Datetime(string="dateModified", help="")
    description = fields.Char(string="description", help="free-text description of the resource")
    device_state = fields.Char(string="deviceState", help="")
    device_type = fields.Char(string="deviceType", help="NGSI Entity type")
    end_date = fields.Datetime(string="endDate", help="A date time( DateTime). The date till the resource is effective")
    firmware_version = fields.Char(string="firmwareVersion", help="")
    hardware_version = fields.Char(string="hardwareVersion", help="")
    lifecycle_state = fields.Char(string="lifecycleState", help="The life cycle state of the resource.")
    manufacture_date = fields.Datetime(string="manufactureDate", help="This is a string attribute that defines the date of manufacture of this item in the fixed format 'dd")
    mnc = fields.Char(string="mnc", help="")
    name = fields.Char(string="name", help="A string used to give a name to the resource")
    os_version = fields.Char(string="osVersion", help="")
    power_state = fields.Char(string="powerState", help="This defines the current power status of the hardware item. Values include: 0:  Unknown 1:  Not")
    provider = fields.Char(string="provider", help="")
    serial_number = fields.Char(string="serialNumber", help="")
    software_version = fields.Char(string="softwareVersion", help="")
    source = fields.Char(string="source", help="")
    start_date = fields.Datetime(string="startDate", help="A date time( DateTime). The date from which the resource is effective")
    value = fields.Char(string="value", help="")
    version = fields.Char(string="version", help="A field that identifies the specific version of an instance of a resource.")
    version_number = fields.Char(string="versionNumber", help="This is a string that identifies the version of this object. This is an optional attribute.")
    address = fields.Char(string="address", help="")
    characteristic = fields.Char(string="characteristic", help="")
    configuration = fields.Char(string="configuration", help="")
    location = fields.Char(string="location", help="")
    mac_address = fields.Char(string="macAddress", help="")
    note = fields.Char(string="note", help="")
    party_role = fields.Char(string="partyRole", help="")
    place = fields.Char(string="place", help="")
    related_party = fields.Char(string="relatedParty", help="")
    resource_relationship = fields.Char(string="resourceRelationship", help="")
    rule = fields.Char(string="rule", help="")

    def _get_tmf_api_path(self):
        return "/deviceManagement/v4/Device"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Device",
            "alternateName": self.alternate_name,
            "areaServed": self.area_served,
            "batteryLevel": self.battery_level,
            "category": self.category,
            "dataProvider": self.data_provider,
            "dateCreated": self.date_created.isoformat() if self.date_created else None,
            "dateFirstUsed": self.date_first_used.isoformat() if self.date_first_used else None,
            "dateInstalled": self.date_installed.isoformat() if self.date_installed else None,
            "dateLastCalibration": self.date_last_calibration.isoformat() if self.date_last_calibration else None,
            "dateLastValueReported": self.date_last_value_reported.isoformat() if self.date_last_value_reported else None,
            "dateManufactured": self.date_manufactured.isoformat() if self.date_manufactured else None,
            "dateModified": self.date_modified.isoformat() if self.date_modified else None,
            "description": self.description,
            "deviceState": self.device_state,
            "deviceType": self.device_type,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "firmwareVersion": self.firmware_version,
            "hardwareVersion": self.hardware_version,
            "lifecycleState": self.lifecycle_state,
            "manufactureDate": self.manufacture_date.isoformat() if self.manufacture_date else None,
            "mnc": self.mnc,
            "name": self.name,
            "osVersion": self.os_version,
            "powerState": self.power_state,
            "provider": self.provider,
            "serialNumber": self.serial_number,
            "softwareVersion": self.software_version,
            "source": self.source,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "value": self.value,
            "version": self.version,
            "versionNumber": self.version_number,
            "address": self.address,
            "characteristic": self.characteristic,
            "configuration": self.configuration,
            "location": self.location,
            "macAddress": self.mac_address,
            "note": self.note,
            "partyRole": self.party_role,
            "place": self.place,
            "relatedParty": self.related_party,
            "resourceRelationship": self.resource_relationship,
            "rule": self.rule,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('device', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('device', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='device',
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
