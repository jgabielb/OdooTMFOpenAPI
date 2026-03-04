from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.physical.resource'
    _description = 'PhysicalResource'
    _inherit = ['tmf.model.mixin']

    category = fields.Char(string="category", help="Category of the concrete resource. e.g Gold, Silver for MSISDN concrete resource")
    description = fields.Char(string="description", help="free-text description of the resource")
    end_operating_date = fields.Datetime(string="endOperatingDate", help="A date time( DateTime). The date till the resource is operating")
    manufacture_date = fields.Datetime(string="manufactureDate", help="This is a string attribute that defines the date of manufacture of this item in the fixed format 'dd")
    name = fields.Char(string="name", help="A string used to give a name to the resource")
    power_state = fields.Char(string="powerState", help="This defines the current power status of the hardware item.")
    resource_version = fields.Char(string="resourceVersion", help="A field that identifies the specific version of an instance of a resource.")
    serial_number = fields.Char(string="serialNumber", help="This is a string that represents a manufacturer-allocated number used to identify different instance")
    start_operating_date = fields.Datetime(string="startOperatingDate", help="A date time( DateTime). The date from which the resource is operating")
    version_number = fields.Char(string="versionNumber", help="This is a string that identifies the version of this physical resource. This is an optional attribut")
    activation_feature = fields.Char(string="activationFeature", help="Configuration features")
    administrative_state = fields.Char(string="administrativeState", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    attachment = fields.Char(string="attachment", help="")
    note = fields.Char(string="note", help="")
    operational_state = fields.Char(string="operationalState", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    place = fields.Char(string="place", help="")
    related_party = fields.Char(string="relatedParty", help="")
    resource_characteristic = fields.Char(string="resourceCharacteristic", help="")
    resource_relationship = fields.Char(string="resourceRelationship", help="")
    resource_specification = fields.Char(string="resourceSpecification", help="")
    resource_status = fields.Char(string="resourceStatus", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    usage_state = fields.Char(string="usageState", help="Tracks the lifecycle status of the resource, such as planning, installing, opereating, retiring and ")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    product_id = fields.Many2one("product.product", string="Product", ondelete="set null")
    stock_lot_id = fields.Many2one("stock.lot", string="Stock Lot", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/physical_resourceManagement/v4/PhysicalResource"

    def _safe_json(self, value, default):
        if not value:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    def _resolve_partner(self):
        self.ensure_one()
        refs = self._safe_json(self.related_party, [])
        if isinstance(refs, dict):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        env_partner = self.env["res.partner"].sudo()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (ref.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _sync_native_links(self):
        env_product = self.env["product.product"].sudo()
        env_lot = self.env["stock.lot"].sudo()
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            if rec.name and not rec.product_id:
                product = env_product.search([("name", "=", rec.name)], limit=1)
                if product:
                    rec.product_id = product.id
            if rec.serial_number and not rec.stock_lot_id:
                lot = env_lot.search([("name", "=", rec.serial_number)], limit=1)
                if lot:
                    rec.stock_lot_id = lot.id

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "PhysicalResource",
            "category": self.category,
            "description": self.description,
            "endOperatingDate": self.end_operating_date.isoformat() if self.end_operating_date else None,
            "manufactureDate": self.manufacture_date.isoformat() if self.manufacture_date else None,
            "name": self.name,
            "powerState": self.power_state,
            "resourceVersion": self.resource_version,
            "serialNumber": self.serial_number,
            "startOperatingDate": self.start_operating_date.isoformat() if self.start_operating_date else None,
            "versionNumber": self.version_number,
            "activationFeature": self.activation_feature,
            "administrativeState": self.administrative_state,
            "attachment": self.attachment,
            "note": self.note,
            "operationalState": self.operational_state,
            "place": self.place,
            "relatedParty": self.related_party,
            "resourceCharacteristic": self.resource_characteristic,
            "resourceRelationship": self.resource_relationship,
            "resourceSpecification": self.resource_specification,
            "resourceStatus": self.resource_status,
            "usageState": self.usage_state,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_native_links()
        for rec in recs:
            self._notify('physicalResource', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "related_party" in vals or "name" in vals or "serial_number" in vals or "partner_id" in vals or "product_id" in vals or "stock_lot_id" in vals:
            self._sync_native_links()
        for rec in self:
            self._notify('physicalResource', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='physicalResource',
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
