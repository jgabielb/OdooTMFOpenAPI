import json
from odoo import api, fields, models


API_BASE = "/tmf-api/ResourceActivationAndConfiguration/v4"
BASE_PATH = f"{API_BASE}/resource"


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


class TMF702Resource(models.Model):
    _name = "tmf702.resource"
    _description = "TMF702 Resource"
    _inherit = ["tmf.model.mixin"]

    category = fields.Char(string="category")
    description = fields.Char(string="description")
    end_operating_date = fields.Datetime(string="endOperatingDate")
    name = fields.Char(string="name")
    resource_version = fields.Char(string="resourceVersion")
    start_operating_date = fields.Datetime(string="startOperatingDate")
    administrative_state = fields.Char(string="administrativeState")
    operational_state = fields.Char(string="operationalState")
    resource_status = fields.Char(string="resourceStatus")
    usage_state = fields.Char(string="usageState")
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    project_task_id = fields.Many2one("project.task", string="Fulfillment Task", ondelete="set null")
    picking_id = fields.Many2one("stock.picking", string="Stock Picking", ondelete="set null")

    resource_specification_json = fields.Text(string="resourceSpecification")
    resource_characteristic_json = fields.Text(string="resourceCharacteristic")
    activation_feature_json = fields.Text(string="activationFeature")
    attachment_json = fields.Text(string="attachment")
    note_json = fields.Text(string="note")
    related_party_json = fields.Text(string="relatedParty")
    place_json = fields.Text(string="place")
    resource_relationship_json = fields.Text(string="resourceRelationship")

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        parties = _loads(self.related_party_json) or []
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

    def _sync_fulfillment_records(self):
        Task = self.env["project.task"].sudo()
        Project = self.env["project.project"].sudo()
        Picking = self.env["stock.picking"].sudo()
        PickingType = self.env["stock.picking.type"].sudo()
        for rec in self:
            partner = rec.partner_id
            if not partner:
                partner = rec._resolve_partner_from_related_party()
                if partner and partner.exists():
                    rec.partner_id = partner.id

            project = Project.search([], limit=1)
            task_vals = {
                "name": rec.name or f"TMF Resource {rec.tmf_id or rec.id}",
                "description": rec.description or "",
                "partner_id": partner.id if partner and partner.exists() else False,
                "date_deadline": rec.end_operating_date.date() if rec.end_operating_date else False,
            }
            if project:
                task_vals["project_id"] = project.id
            if rec.project_task_id and rec.project_task_id.exists():
                rec.project_task_id.write(task_vals)
            else:
                rec.project_task_id = Task.create(task_vals).id

            picking_type = PickingType.search([("code", "=", "outgoing")], limit=1) or PickingType.search([], limit=1)
            if picking_type:
                pick_vals = {
                    "partner_id": partner.id if partner and partner.exists() else False,
                    "origin": rec.tmf_id,
                    "scheduled_date": rec.start_operating_date or False,
                    "note": rec.description or "",
                    "picking_type_id": picking_type.id,
                    "location_id": picking_type.default_location_src_id.id,
                    "location_dest_id": picking_type.default_location_dest_id.id,
                }
                if rec.picking_id and rec.picking_id.exists():
                    rec.picking_id.write(pick_vals)
                else:
                    rec.picking_id = Picking.create(pick_vals).id

    def _get_tmf_api_path(self):
        return BASE_PATH

    def to_tmf_json(self):
        self.ensure_one()
        rid = self.tmf_id
        return {
            "id": rid,
            "href": f"{BASE_PATH}/{rid}" if rid else None,
            "@type": "Resource",
            "name": self.name,
            "description": self.description,
            "category": self.category,
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
        }

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("category", "category"),
            ("description", "description"),
            ("name", "name"),
            ("resourceVersion", "resource_version"),
            ("administrativeState", "administrative_state"),
            ("operationalState", "operational_state"),
            ("resourceStatus", "resource_status"),
            ("usageState", "usage_state"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)

        if "startOperatingDate" in data:
            vals["start_operating_date"] = data.get("startOperatingDate")
        if "endOperatingDate" in data:
            vals["end_operating_date"] = data.get("endOperatingDate")

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

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_fulfillment_records()
        for rec in recs:
            self._notify("resource", "create", rec)
        return recs

    def write(self, vals):
        state_fields = {"administrative_state", "operational_state", "resource_status", "usage_state"}
        state_changed = bool(set(vals.keys()) & state_fields)
        res = super().write(vals)
        self._sync_fulfillment_records()
        for rec in self:
            self._notify("resource", "update", rec)
            if state_changed:
                self._notify("resource", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="resource",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMF702Monitor(models.Model):
    _name = "tmf702.monitor"
    _description = "TMF702 Monitor"
    _inherit = ["tmf.model.mixin"]

    source_href = fields.Char(string="sourceHref")
    state = fields.Char(string="state")
    request_json = fields.Text(string="request")
    response_json = fields.Text(string="response")

    def _get_tmf_api_path(self):
        return f"{API_BASE}/monitor"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Monitor",
            "sourceHref": self.source_href,
            "state": self.state,
            "request": _loads(self.request_json),
            "response": _loads(self.response_json),
        }
