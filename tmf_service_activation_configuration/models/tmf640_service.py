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
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    project_task_id = fields.Many2one("project.task", string="Fulfillment Task", ondelete="set null")

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

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        parties = []
        try:
            parties = json.loads(self.related_party_json) if self.related_party_json else []
        except Exception:
            parties = []
        if not isinstance(parties, list):
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo()
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            if not pid:
                continue
            partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
            if not partner and str(pid).isdigit():
                partner = Partner.browse(int(pid))
            if partner and partner.exists():
                return partner
        return self.env["res.partner"]

    def _sync_project_task(self):
        Task = self.env["project.task"].sudo()
        Project = self.env["project.project"].sudo()
        for rec in self:
            partner = rec.partner_id
            if not partner:
                partner = rec._resolve_partner_from_related_party()
                if partner and partner.exists():
                    rec.partner_id = partner.id
            project = Project.search([], limit=1)
            task_vals = {
                "name": rec.name or f"TMF Service {rec.tmf640_id or rec.tmf_id or rec.id}",
                "description": rec.description or "",
                "partner_id": partner.id if partner and partner.exists() else False,
                "date_deadline": rec.end_date.date() if rec.end_date else False,
            }
            if project:
                task_vals["project_id"] = project.id
            if rec.project_task_id and rec.project_task_id.exists():
                rec.project_task_id.write(task_vals)
            else:
                rec.project_task_id = Task.create(task_vals).id

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ServiceCreateEvent",
            "update": "ServiceAttributeValueChangeEvent",
            "delete": "ServiceDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("service", event_name, payload)
            except Exception:
                continue

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

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_project_task()
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._sync_project_task()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
