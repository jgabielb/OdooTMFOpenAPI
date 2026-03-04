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


class _TMF715WarrantyMixin(models.AbstractModel):
    _name = "tmf.warranty.common.mixin"
    _description = "TMF715 Common Warranty Mixin"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    name = fields.Char(string="name")
    version = fields.Char(string="version")
    state = fields.Char(string="state")
    status = fields.Char(string="status")
    status_change_date = fields.Char(string="statusChangeDate")
    is_bundle = fields.Boolean(string="isBundle")
    is_external = fields.Boolean(string="isExternal")

    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "name": self.name,
            "version": self.version,
            "state": self.state,
            "status": self.status,
            "statusChangeDate": self.status_change_date,
            "isBundle": self.is_bundle,
            "isExternal": self.is_external,
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
            ("status", "status"),
            ("statusChangeDate", "status_change_date"),
            ("isBundle", "is_bundle"),
            ("isExternal", "is_external"),
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

    def _resolve_partner_from_json_text(self, json_text):
        refs = _loads(json_text)
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

    def _sync_partner_link(self):
        for rec in self:
            if not hasattr(rec, "related_party_json"):
                continue
            partner = rec._resolve_partner_from_json_text(getattr(rec, "related_party_json"))
            if partner:
                rec.partner_id = partner.id


class TMFWarranty(models.Model):
    _name = "tmf.warranty"
    _description = "TMF715 Warranty"
    _inherit = ["tmf.warranty.common.mixin"]

    context = fields.Char(string="context")
    start_date = fields.Char(string="startDate")
    end_date = fields.Char(string="endDate")

    applies_to_product_json = fields.Text(string="appliesToProduct")
    applies_to_resource_json = fields.Text(string="appliesToResource")
    attachment_json = fields.Text(string="attachment")
    characteristic_json = fields.Text(string="characteristic")
    entity_relationship_json = fields.Text(string="entityRelationship")
    entity_specification_json = fields.Text(string="entitySpecification")
    note_json = fields.Text(string="note")
    place_json = fields.Text(string="place")
    related_party_json = fields.Text(string="relatedParty")
    valid_for_json = fields.Text(string="validFor")
    warranty_json = fields.Text(string="warranty")
    warranty_agreement_json = fields.Text(string="warrantyAgreement")
    warranty_relationship_json = fields.Text(string="warrantyRelationship")
    warranty_specification_json = fields.Text(string="warrantySpecification")
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/warrantyManagement/v4/warranty"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "Warranty"
        payload["context"] = self.context
        payload["startDate"] = self.start_date
        payload["endDate"] = self.end_date
        payload["appliesToProduct"] = _loads(self.applies_to_product_json)
        payload["appliesToResource"] = _loads(self.applies_to_resource_json)
        payload["attachment"] = _loads(self.attachment_json)
        payload["characteristic"] = _loads(self.characteristic_json)
        payload["entityRelationship"] = _loads(self.entity_relationship_json)
        payload["entitySpecification"] = _loads(self.entity_specification_json)
        payload["note"] = _loads(self.note_json)
        payload["place"] = _loads(self.place_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["validFor"] = _loads(self.valid_for_json)
        payload["warranty"] = _loads(self.warranty_json)
        payload["warrantyAgreement"] = _loads(self.warranty_agreement_json)
        payload["warrantyRelationship"] = _loads(self.warranty_relationship_json)
        payload["warrantySpecification"] = _loads(self.warranty_specification_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("context", "context"),
            ("startDate", "start_date"),
            ("endDate", "end_date"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("appliesToProduct", "applies_to_product_json"),
            ("appliesToResource", "applies_to_resource_json"),
            ("attachment", "attachment_json"),
            ("characteristic", "characteristic_json"),
            ("entityRelationship", "entity_relationship_json"),
            ("entitySpecification", "entity_specification_json"),
            ("note", "note_json"),
            ("place", "place_json"),
            ("relatedParty", "related_party_json"),
            ("validFor", "valid_for_json"),
            ("warranty", "warranty_json"),
            ("warrantyAgreement", "warranty_agreement_json"),
            ("warrantyRelationship", "warranty_relationship_json"),
            ("warrantySpecification", "warranty_specification_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_partner_link()
        for rec in recs:
            self._notify("warranty", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "status" in vals
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        for rec in self:
            self._notify("warranty", "update", rec)
            if state_changed:
                self._notify("warranty", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="warranty",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFWarrantySpecification(models.Model):
    _name = "tmf.warranty.specification"
    _description = "TMF715 WarrantySpecification"
    _inherit = ["tmf.warranty.common.mixin"]

    lifecycle_status = fields.Char(string="lifecycleStatus")
    last_update = fields.Char(string="lastUpdate")

    attachment_json = fields.Text(string="attachment")
    constraint_json = fields.Text(string="constraint")
    entity_spec_relationship_json = fields.Text(string="entitySpecRelationship")
    product_spec_json = fields.Text(string="productSpec")
    related_party_json = fields.Text(string="relatedParty")
    resource_spec_json = fields.Text(string="resourceSpec")
    spec_characteristic_json = fields.Text(string="specCharacteristic")
    target_entity_schema_json = fields.Text(string="targetEntitySchema")
    valid_for_json = fields.Text(string="validFor")
    warranty_agreement_specification_json = fields.Text(string="warrantyAgreementSpecification")
    warranty_duration_json = fields.Text(string="warrantyDuration")
    warranty_spec_relationship_json = fields.Text(string="warrantySpecRelationship")
    warranty_specification_json = fields.Text(string="warrantySpecification")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

    def _sync_product_link(self):
        env_pt = self.env["product.template"].sudo()
        for rec in self:
            pt = False
            if rec.tmf_id:
                pt = env_pt.search([("tmf_id", "=", rec.tmf_id)], limit=1)
            if not pt and rec.name:
                pt = env_pt.search([("name", "=", rec.name)], limit=1)
            if not pt and rec.name:
                pt = env_pt.create({"name": rec.name})
            if pt:
                rec.product_tmpl_id = pt.id

    def _get_tmf_api_path(self):
        return "/warrantyManagement/v4/warrantySpecification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "WarrantySpecification"
        payload["lifecycleStatus"] = self.lifecycle_status
        payload["lastUpdate"] = self.last_update
        payload["attachment"] = _loads(self.attachment_json)
        payload["constraint"] = _loads(self.constraint_json)
        payload["entitySpecRelationship"] = _loads(self.entity_spec_relationship_json)
        payload["productSpec"] = _loads(self.product_spec_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["resourceSpec"] = _loads(self.resource_spec_json)
        payload["specCharacteristic"] = _loads(self.spec_characteristic_json)
        payload["targetEntitySchema"] = _loads(self.target_entity_schema_json)
        payload["validFor"] = _loads(self.valid_for_json)
        payload["warrantyAgreementSpecification"] = _loads(self.warranty_agreement_specification_json)
        payload["warrantyDuration"] = _loads(self.warranty_duration_json)
        payload["warrantySpecRelationship"] = _loads(self.warranty_spec_relationship_json)
        payload["warrantySpecification"] = _loads(self.warranty_specification_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("lifecycleStatus", "lifecycle_status"),
            ("lastUpdate", "last_update"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("attachment", "attachment_json"),
            ("constraint", "constraint_json"),
            ("entitySpecRelationship", "entity_spec_relationship_json"),
            ("productSpec", "product_spec_json"),
            ("relatedParty", "related_party_json"),
            ("resourceSpec", "resource_spec_json"),
            ("specCharacteristic", "spec_characteristic_json"),
            ("targetEntitySchema", "target_entity_schema_json"),
            ("validFor", "valid_for_json"),
            ("warrantyAgreementSpecification", "warranty_agreement_specification_json"),
            ("warrantyDuration", "warranty_duration_json"),
            ("warrantySpecRelationship", "warranty_spec_relationship_json"),
            ("warrantySpecification", "warranty_specification_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_partner_link()
        recs._sync_product_link()
        for rec in recs:
            self._notify("warrantySpecification", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "lifecycle_status" in vals
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        if "name" in vals or "tmf_id" in vals or "product_tmpl_id" in vals:
            self._sync_product_link()
        for rec in self:
            self._notify("warrantySpecification", "update", rec)
            if state_changed:
                self._notify("warrantySpecification", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="warrantySpecification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

