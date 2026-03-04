import json
from datetime import datetime, timezone
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


class _TMF725CommonMixin(models.AbstractModel):
    _name = "tmf.metadata.catalog.common.mixin"
    _description = "TMF725 Common Metadata Catalog Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    last_update = fields.Char(string="lastUpdate")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "lastUpdate": self.last_update,
            "lifecycleStatus": self.lifecycle_status,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("lastUpdate", "last_update"),
            ("lifecycleStatus", "lifecycle_status"),
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


class TMFMetadataCatalog(models.Model):
    _name = "tmf.metadata.catalog"
    _description = "TMF725 MetadataCatalog"
    _inherit = ["tmf.metadata.catalog.common.mixin"]

    version = fields.Char(string="version")
    last_update_date = fields.Char(string="lastUpdateDate")
    attachment_json = fields.Text(string="attachment")
    metadata_category_json = fields.Text(string="metadataCategory")
    related_party_json = fields.Text(string="relatedParty")
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
        return "/metadataCatalog/v4/metadataCatalog"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.pop("lastUpdate", None)
        payload.update(
            {
                "version": self.version,
                "lastUpdateDate": self.last_update_date or self.last_update,
                "attachment": _loads(self.attachment_json),
                "metadataCategory": _loads(self.metadata_category_json),
                "relatedParty": _loads(self.related_party_json),
                "@type": self.tmf_type_value or "MetadataCatalog",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        if "version" in data:
            vals["version"] = data.get("version")
        if "lastUpdateDate" in data:
            vals["last_update_date"] = data.get("lastUpdateDate")
        if "attachment" in data:
            vals["attachment_json"] = _dumps(data.get("attachment"))
        if "metadataCategory" in data:
            vals["metadata_category_json"] = _dumps(data.get("metadataCategory"))
        if "relatedParty" in data:
            vals["related_party_json"] = _dumps(data.get("relatedParty"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_update_date", vals.get("last_update_date") or vals.get("last_update") or self._now_iso())
        recs = super().create(vals_list)
        recs._sync_partner_link()
        recs._sync_product_link()
        for rec in recs:
            self._notify("metadataCatalog", "create", rec)
        return recs

    def write(self, vals):
        status_changed = "lifecycle_status" in vals
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        if "name" in vals or "tmf_id" in vals or "product_tmpl_id" in vals:
            self._sync_product_link()
        for rec in self:
            self._notify("metadataCatalog", "update", rec)
            if status_changed:
                self._notify("metadataCatalog", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="metadataCatalog",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFMetadataCategory(models.Model):
    _name = "tmf.metadata.category"
    _description = "TMF725 MetadataCategory"
    _inherit = ["tmf.metadata.catalog.common.mixin"]

    is_root = fields.Boolean(string="isRoot")
    parent_id_text = fields.Char(string="parentId")
    metadata_catalog_item_json = fields.Text(string="MetadataCatalogItem")
    child_category_json = fields.Text(string="childCategory")
    valid_for_json = fields.Text(string="validFor")

    def _get_tmf_api_path(self):
        return "/metadataCatalog/v4/metadataCategory"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "isRoot": self.is_root,
                "parentId": self.parent_id_text,
                "MetadataCatalogItem": _loads(self.metadata_catalog_item_json),
                "childCategory": _loads(self.child_category_json),
                "validFor": _loads(self.valid_for_json),
                "@type": self.tmf_type_value or "MetadataCategory",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("isRoot", "is_root"),
            ("parentId", "parent_id_text"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("MetadataCatalogItem", "metadata_catalog_item_json"),
            ("childCategory", "child_category_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_update", vals.get("last_update") or self._now_iso())
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("metadataCategory", "create", rec)
        return recs

    def write(self, vals):
        status_changed = "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("metadataCategory", "update", rec)
            if status_changed:
                self._notify("metadataCategory", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="metadataCategory",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFMetadataCatalogItem(models.Model):
    _name = "tmf.metadata.catalog.item"
    _description = "TMF725 MetadataCatalogItem"
    _inherit = ["tmf.metadata.catalog.common.mixin"]

    category_json = fields.Text(string="category")
    specification_json = fields.Text(string="specification")
    valid_for_json = fields.Text(string="validFor")

    def _get_tmf_api_path(self):
        return "/metadataCatalog/v4/metadataCatalogItem"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "category": _loads(self.category_json),
                "specification": _loads(self.specification_json),
                "validFor": _loads(self.valid_for_json),
                "@type": self.tmf_type_value or "MetadataCatalogItem",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("category", "category_json"),
            ("specification", "specification_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_update", vals.get("last_update") or self._now_iso())
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("metadataCatalogItem", "create", rec)
        return recs

    def write(self, vals):
        status_changed = "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("metadataCatalogItem", "update", rec)
            if status_changed:
                self._notify("metadataCatalogItem", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="metadataCatalogItem",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFMetadataSpecification(models.Model):
    _name = "tmf.metadata.specification"
    _description = "TMF725 MetadataSpecification"
    _inherit = ["tmf.metadata.catalog.common.mixin"]

    is_composed = fields.Boolean(string="isComposed")
    attachment_json = fields.Text(string="attachment")
    composite_metadata_specification_json = fields.Text(string="compositeMetadataSpecification")
    entity_spec_relationship_json = fields.Text(string="entitySpecRelationship")
    metadata_spec_characteristic_json = fields.Text(string="metadataSpecCharacteristic")
    policy_specification_ref_json = fields.Text(string="policySpecificationRef")
    related_party_json = fields.Text(string="relatedParty")
    target_entity_schema_json = fields.Text(string="targetEntitySchema")
    valid_for_json = fields.Text(string="validFor")
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
        return "/metadataCatalog/v4/metadataSpecification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "isComposed": self.is_composed,
                "attachment": _loads(self.attachment_json),
                "compositeMetadataSpecification": _loads(self.composite_metadata_specification_json),
                "entitySpecRelationship": _loads(self.entity_spec_relationship_json),
                "metadataSpecCharacteristic": _loads(self.metadata_spec_characteristic_json),
                "policySpecificationRef": _loads(self.policy_specification_ref_json),
                "relatedParty": _loads(self.related_party_json),
                "targetEntitySchema": _loads(self.target_entity_schema_json),
                "validFor": _loads(self.valid_for_json),
                "@type": self.tmf_type_value or "MetadataSpecification",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        if "isComposed" in data:
            vals["is_composed"] = data.get("isComposed")
        for key, field_name in [
            ("attachment", "attachment_json"),
            ("compositeMetadataSpecification", "composite_metadata_specification_json"),
            ("entitySpecRelationship", "entity_spec_relationship_json"),
            ("metadataSpecCharacteristic", "metadata_spec_characteristic_json"),
            ("policySpecificationRef", "policy_specification_ref_json"),
            ("relatedParty", "related_party_json"),
            ("targetEntitySchema", "target_entity_schema_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_update", vals.get("last_update") or self._now_iso())
        recs = super().create(vals_list)
        recs._sync_partner_link()
        recs._sync_product_link()
        for rec in recs:
            self._notify("metadataSpecification", "create", rec)
        return recs

    def write(self, vals):
        status_changed = "lifecycle_status" in vals
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        if "name" in vals or "tmf_id" in vals or "product_tmpl_id" in vals:
            self._sync_product_link()
        for rec in self:
            self._notify("metadataSpecification", "update", rec)
            if status_changed:
                self._notify("metadataSpecification", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="metadataSpecification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

