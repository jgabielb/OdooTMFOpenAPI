from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.ai.contract.specification'
    _description = 'AiContractSpecification'
    _inherit = ['tmf.model.mixin']

    description = fields.Char(string="description", help="Description of the specification")
    is_bundle = fields.Boolean(string="isBundle", help="isBundle determines whether specification represents a single specification (false), or a bundle of ")
    last_update = fields.Datetime(string="lastUpdate", help="Date and time of the last update of the specification")
    lifecycle_status = fields.Char(string="lifecycleStatus", help="Used to indicate the current lifecycle status of this catalog item")
    name = fields.Char(string="name", help="Name given to the specification")
    version = fields.Char(string="version", help="specification version")
    attachment = fields.Char(string="attachment", help="Attachments that may be of relevance to this specification, such as picture, document, media")
    constraint = fields.Char(string="constraint", help="This is a list of constraint references applied to this specification")
    entity_spec_relationship = fields.Char(string="entitySpecRelationship", help="Relationship to another specification")
    related_party = fields.Char(string="relatedParty", help="Parties who manage or otherwise have an interest in this specification")
    spec_characteristic = fields.Char(string="specCharacteristic", help="List of characteristics that the entity can take")
    target_entity_schema = fields.Char(string="targetEntitySchema", help="Pointer to a schema that defines the target entity")
    valid_for = fields.Char(string="validFor", help="The period for which this REST resource is valid")

    def _get_tmf_api_path(self):
        return "/ai_contract_specificationManagement/v4/AiContractSpecification"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "AiContractSpecification",
            "description": self.description,
            "isBundle": self.is_bundle,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status,
            "name": self.name,
            "version": self.version,
            "attachment": self.attachment,
            "constraint": self.constraint,
            "entitySpecRelationship": self.entity_spec_relationship,
            "relatedParty": self.related_party,
            "specCharacteristic": self.spec_characteristic,
            "targetEntitySchema": self.target_entity_schema,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('aiContractSpecification', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('aiContractSpecification', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='aiContractSpecification',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
