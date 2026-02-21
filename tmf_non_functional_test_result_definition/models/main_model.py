from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.non.functional.test.result.definition'
    _description = 'NonFunctionalTestResultDefinition'
    _inherit = ['tmf.model.mixin']

    attachment_type = fields.Char(string="attachmentType", help="Attachment type such as video, picture")
    content = fields.Char(string="content", help="The actual contents of the attachment object, if embedded, encoded as base64")
    description = fields.Char(string="description", help="A narrative text describing the content of the attachment")
    mime_type = fields.Char(string="mimeType", help="Attachment mime type such as extension file for video, picture and document")
    name = fields.Char(string="name", help="The name of the attachment")
    url = fields.Char(string="url", help="Uniform Resource Locator, is a web page address (a subset of URI)")
    size = fields.Char(string="size", help="The size of the attachment.")
    valid_for = fields.Char(string="validFor", help="The period of time for which the attachment is valid")

    def _get_tmf_api_path(self):
        return "/non_functional_test_result_definitionManagement/v4/NonFunctionalTestResultDefinition"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "NonFunctionalTestResultDefinition",
            "attachmentType": self.attachment_type,
            "content": self.content,
            "description": self.description,
            "mimeType": self.mime_type,
            "name": self.name,
            "url": self.url,
            "size": self.size,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('nonFunctionalTestResultDefinition', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('nonFunctionalTestResultDefinition', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='nonFunctionalTestResultDefinition',
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
