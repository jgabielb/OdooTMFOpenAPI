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


class TMFGeneralTestArtifact(models.Model):
    _name = "tmf.general.test.artifact"
    _description = "TMF710 GeneralTestArtifact"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    version = fields.Char(string="version")
    version_description = fields.Char(string="versionDescription")
    agreement_json = fields.Text(string="agreement")
    attribute_json = fields.Text(string="attribute")
    general_artifact_definition_json = fields.Text(string="generalArtifactDefinition")
    related_party_json = fields.Text(string="relatedParty")
    state = fields.Char(string="state")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/generalTestArtifact/v4/generalTestArtifact"

    def _resolve_partner(self):
        self.ensure_one()
        refs = _loads(self.related_party_json)
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
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "version": self.version,
            "versionDescription": self.version_description,
            "agreement": _loads(self.agreement_json),
            "attribute": _loads(self.attribute_json),
            "generalArtifactDefinition": _loads(self.general_artifact_definition_json),
            "relatedParty": _loads(self.related_party_json),
            "state": self.state,
            "@type": self.tmf_type_value or "GeneralTestArtifact",
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("version", "version"),
            ("versionDescription", "version_description"),
            ("state", "state"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if "agreement" in data:
            vals["agreement_json"] = _dumps(data.get("agreement"))
        if "attribute" in data:
            vals["attribute_json"] = _dumps(data.get("attribute"))
        if "generalArtifactDefinition" in data:
            vals["general_artifact_definition_json"] = _dumps(data.get("generalArtifactDefinition"))
        if "relatedParty" in data:
            vals["related_party_json"] = _dumps(data.get("relatedParty"))
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="generalTestArtifact",
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
        state_changed = "state" in vals
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals or "product_tmpl_id" in vals:
            self._sync_native_links()
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="generalTestArtifact",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
