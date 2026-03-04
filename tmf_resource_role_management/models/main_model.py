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


class TMFResourceRoleMixin(models.AbstractModel):
    _name = "tmf.resource.role.mixin"
    _description = "TMF768 Resource Role Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    status = fields.Char(string="status")
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

    _api_name = None
    _default_type = None

    def _resolve_partner(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        refs = payload.get("relatedParty")
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

    def _resolve_product_template(self):
        self.ensure_one()
        env_pt = self.env["product.template"].sudo()
        if self.tmf_id:
            pt = env_pt.search([("tmf_id", "=", self.tmf_id)], limit=1)
            if pt:
                return pt
        if self.name:
            pt = env_pt.search([("name", "=", self.name)], limit=1)
            if pt:
                return pt
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            pt = rec._resolve_product_template()
            if pt:
                rec.product_tmpl_id = pt.id

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
        payload["@type"] = self.tmf_type_value or payload.get("@type") or self._default_type
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
            ("status", "status"),
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
        recs._sync_native_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "status" in vals
        res = super().write(vals)
        if "payload_json" in vals or "name" in vals or "partner_id" in vals or "product_tmpl_id" in vals:
            self._sync_native_links()
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


class TMFResourceRole(models.Model):
    _name = "tmf.resource.role"
    _description = "TMF768 ResourceRole"
    _inherit = ["tmf.resource.role.mixin"]

    _api_name = "resourceRole"
    _default_type = "ResourceRole"

    def _get_tmf_api_path(self):
        return "/resourceRoleManagement/v5/resourceRole"


class TMFResourceRoleSpecification(models.Model):
    _name = "tmf.resource.role.specification"
    _description = "TMF768 ResourceRoleSpecification"
    _inherit = ["tmf.resource.role.mixin"]

    _api_name = "resourceRoleSpecification"
    _default_type = "ResourceRoleSpecification"

    def _get_tmf_api_path(self):
        return "/resourceRoleManagement/v5/resourceRoleSpecification"

