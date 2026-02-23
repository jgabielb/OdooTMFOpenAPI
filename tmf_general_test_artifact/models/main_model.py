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

    def _get_tmf_api_path(self):
        return "/generalTestArtifact/v4/generalTestArtifact"

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
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
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
