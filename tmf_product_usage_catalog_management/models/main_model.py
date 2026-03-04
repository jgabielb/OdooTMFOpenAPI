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


class TMFProductUsageSpecification(models.Model):
    _name = "tmf.product.usage.specification"
    _description = "TMF767 ProductUsageSpecification"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    lifecycle_status = fields.Char(string="lifecycleStatus", required=True)
    version = fields.Char(string="version")
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/productUsageCatalogManagement/v5/productUsageSpecification"

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

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        payload["name"] = self.name
        payload["lifecycleStatus"] = self.lifecycle_status
        if self.description is not None:
            payload["description"] = self.description
        if self.version is not None:
            payload["version"] = self.version
        payload["@type"] = self.tmf_type_value or payload.get("@type") or "ProductUsageSpecification"
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
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
                api_name="productUsageSpecification",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_product_link()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        lifecycle_changed = "lifecycle_status" in vals
        res = super().write(vals)
        if "name" in vals or "tmf_id" in vals or "product_tmpl_id" in vals:
            self._sync_product_link()
        for rec in self:
            self._notify("update", rec)
            if lifecycle_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="productUsageSpecification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

