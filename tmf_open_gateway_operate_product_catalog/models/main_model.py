import json
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None and v is not False}


def _safe_str(value):
    return str(value).strip() if value is not None else ""


class TMFOGWProductCatalogMixin(models.AbstractModel):
    _name = "tmf.ogw.product.catalog.mixin"
    _description = "TMF936 Open Gateway Product Catalog Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    status = fields.Char(string="status")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    version = fields.Char(string="version")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", copy=False, index=True)
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    _api_name = None
    _default_type = None
    _api_path = None

    def _get_tmf_api_path(self):
        return self._api_path or "/openGatewayOperateAPI/v5"

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        if self.name is not None:
            payload["name"] = self.name
        if self.description is not None:
            payload["description"] = self.description
        if self.status is not None:
            payload["status"] = self.status
        if self.lifecycle_status is not None:
            payload["lifecycleStatus"] = self.lifecycle_status
        if self.version is not None:
            payload["version"] = self.version
        payload["@type"] = self.tmf_type_value or payload.get("@type") or self._default_type
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("status", "status"),
            ("lifecycleStatus", "lifecycle_status"),
            ("version", "version"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=self._api_name,
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_product_template_link()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "status" in vals or "lifecycle_status" in vals
        res = super().write(vals)
        if not self.env.context.get("skip_tmf936_product_sync"):
            self._sync_product_template_link()
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        api_name = self._api_name
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name=api_name,
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

    def _sync_product_template_link(self):
        ProductTemplate = self.env["product.template"].sudo()
        for rec in self:
            payload = _loads(rec.payload_json)
            name = rec.name or _safe_str(payload.get("name")) or rec.tmf_id
            template = rec.product_tmpl_id
            if not template and "tmf_id" in ProductTemplate._fields:
                template = ProductTemplate.search([("tmf_id", "=", rec.tmf_id)], limit=1)
            if not template and name:
                template = ProductTemplate.search([("name", "=", name)], limit=1)
            if template:
                write_vals = {}
                if name and template.name != name:
                    write_vals["name"] = name
                if rec.description and "description_sale" in ProductTemplate._fields and template.description_sale != rec.description:
                    write_vals["description_sale"] = rec.description
                if write_vals:
                    template.write(write_vals)
            else:
                create_vals = {"name": name or "TMF Product"}
                if rec.description and "description_sale" in ProductTemplate._fields:
                    create_vals["description_sale"] = rec.description
                if "tmf_id" in ProductTemplate._fields:
                    create_vals["tmf_id"] = rec.tmf_id
                template = ProductTemplate.create(create_vals)
            if template and rec.product_tmpl_id != template:
                rec.with_context(skip_tmf936_product_sync=True).write({"product_tmpl_id": template.id})


class TMFOGWProductOffering(models.Model):
    _name = "tmf.ogw.product.offering"
    _description = "TMF936 ProductOffering"
    _inherit = ["tmf.ogw.product.catalog.mixin"]

    _api_name = "productOffering"
    _default_type = "ProductOffering"
    _api_path = "/openGatewayOperateAPI/v5/productOffering"


class TMFOGWProductSpecification(models.Model):
    _name = "tmf.ogw.product.specification"
    _description = "TMF936 ProductSpecification"
    _inherit = ["tmf.ogw.product.catalog.mixin"]

    _api_name = "productSpecification"
    _default_type = "ProductSpecification"
    _api_path = "/openGatewayOperateAPI/v5/productSpecification"
