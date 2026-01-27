from odoo import api, fields, models
from odoo.exceptions import ValidationError
import json

class TMF640Service(models.Model):
    _name = "tmf640.service"
    _description = "TMF640 Service"
    _inherit = ["tmf.model.mixin"]  # you already use this mixin in other modules

    # TMF identity / linkage
    tmf640_id = fields.Char(index=True)  # optional, can reuse tmf_id if your mixin provides it
    href = fields.Char()

    # Core
    name = fields.Char()
    description = fields.Text()
    category = fields.Char()
    service_type = fields.Char()  # corresponds to serviceType in TMF JSON

    # TMF640 lifecycle state (string in user guide)
    state = fields.Selection([
        ("feasabilityChecked", "feasabilityChecked"),
        ("designed", "designed"),
        ("reserved", "reserved"),
        ("inactive", "inactive"),
        ("active", "active"),
        ("terminated", "terminated"),
    ], required=True, default="designed")

    # serviceDate/startDate/endDate are in spec (DateTime)
    service_date = fields.Datetime()
    start_date = fields.Datetime()
    end_date = fields.Datetime()

    # Booleans in spec
    has_started = fields.Boolean()
    is_bundle = fields.Boolean()
    is_service_enabled = fields.Boolean(default=True)
    is_stateful = fields.Boolean()

    # TMF polymorphism
    tmf_type = fields.Char(string="@type")
    schema_location = fields.Char(string="@schemaLocation")
    base_type = fields.Char(string="@baseType")

    # serviceSpecification reference (mandatory id)
    service_spec_id = fields.Char(required=True)
    service_spec_name = fields.Char()
    service_spec_href = fields.Char()
    service_spec_version = fields.Char()

    # Characteristics and complex collections: store as JSON for now (simple + flexible)
    service_characteristic_json = fields.Text(string="serviceCharacteristic (json)")
    feature_json = fields.Text(string="feature (json)")
    related_party_json = fields.Text(string="relatedParty (json)")
    supporting_service_json = fields.Text(string="supportingService (json)")
    supporting_resource_json = fields.Text(string="supportingResource (json)")

    @api.constrains("service_spec_id", "state")
    def _check_mandatory(self):
        # TMF640 says create requires: state, serviceSpecification.id :contentReference[oaicite:4]{index=4}
        for rec in self:
            if not rec.service_spec_id:
                raise ValidationError("serviceSpecification.id is mandatory (TMF640).")
            if not rec.state:
                raise ValidationError("state is mandatory (TMF640).")

    def to_tmf_json(self):
        self.ensure_one()
        sid = self.tmf640_id or self.tmf_id or str(self.id)
        href = self.href or f"/tmf-api/ServiceActivationAndConfiguration/v4/service/{sid}"

        def _load(text):
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return None

        payload = {
            "id": sid,
            "href": href,
            "name": self.name or "",
            "description": self.description or "",
            "category": self.category or "",
            "serviceType": self.service_type or "",
            "state": self.state,
            "serviceDate": self.service_date.isoformat() if self.service_date else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "hasStarted": bool(self.has_started),
            "isBundle": bool(self.is_bundle),
            "isServiceEnabled": bool(self.is_service_enabled),
            "isStateful": bool(self.is_stateful),
            "@type": self.tmf_type,
            "@schemaLocation": self.schema_location,
            "@baseType": self.base_type,
            "serviceSpecification": {
                "id": self.service_spec_id,
                "name": self.service_spec_name,
                "href": self.service_spec_href,
                "version": self.service_spec_version,
                "@type": "serviceSpecification",
                "@referredType": "ServiceSpecification",
            },
        }

        # Optional complex arrays (only include if present)
        for k, field_name in [
            ("serviceCharacteristic", "service_characteristic_json"),
            ("feature", "feature_json"),
            ("relatedParty", "related_party_json"),
            ("supportingService", "supporting_service_json"),
            ("supportingResource", "supporting_resource_json"),
        ]:
            val = _load(getattr(self, field_name))
            if val is not None:
                payload[k] = val

        # Remove nulls to keep response clean
        return {k: v for k, v in payload.items() if v is not None and v != ""}
