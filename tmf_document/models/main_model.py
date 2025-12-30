from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.document'
    _description = 'Document'
    _inherit = ['tmf.model.mixin']

    creation_date = fields.Datetime(string="creationDate", help="The date and time the document was created. A date and time formatted in compliance with the ISO8601")
    description = fields.Char(string="description", help="free-text description of the document")
    document_type = fields.Char(string="documentType", help="Name of the document type")
    last_update = fields.Datetime(string="lastUpdate", help="The date and time the document was last modified. A date and time formatted in compliance with the I")
    lifecycle_state = fields.Char(string="lifecycleState", help="The life cycle state of the document.")
    name = fields.Char(string="name", help="A string used to give a name to the document")
    version = fields.Char(string="version", help="A particular form or variety of an artefact that is different from others or from the original. The ")
    binary_attachment = fields.Char(string="binaryAttachment", help="")
    category = fields.Char(string="category", help="")
    characteristic = fields.Char(string="characteristic", help="")
    document_relationship = fields.Char(string="documentRelationship", help="")
    document_specification = fields.Char(string="documentSpecification", help="")
    related_entity = fields.Char(string="relatedEntity", help="")
    related_party = fields.Char(string="relatedParty", help="")

    def _get_tmf_api_path(self):
        return "/documentManagement/v4/Document"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Document",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "documentType": self.document_type,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleState": self.lifecycle_state,
            "name": self.name,
            "version": self.version,
            "binaryAttachment": self.binary_attachment,
            "category": self.category,
            "characteristic": self.characteristic,
            "documentRelationship": self.document_relationship,
            "documentSpecification": self.document_specification,
            "relatedEntity": self.related_entity,
            "relatedParty": self.related_party,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('document', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('document', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='document',
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
