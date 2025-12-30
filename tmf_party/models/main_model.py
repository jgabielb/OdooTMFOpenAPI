from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.party'
    _description = 'Party'
    _inherit = ['tmf.model.mixin']

    contact_medium = fields.Char(string="contactMedium", help="")
    credit_rating = fields.Char(string="creditRating", help="")
    external_reference = fields.Char(string="externalReference", help="")
    party_characteristic = fields.Char(string="partyCharacteristic", help="")
    related_party = fields.Char(string="relatedParty", help="")
    tax_exemption_certificate = fields.Char(string="taxExemptionCertificate", help="")

    def _get_tmf_api_path(self):
        return "/partyManagement/v4/Party"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Party",
            "contactMedium": self.contact_medium,
            "creditRating": self.credit_rating,
            "externalReference": self.external_reference,
            "partyCharacteristic": self.party_characteristic,
            "relatedParty": self.related_party,
            "taxExemptionCertificate": self.tax_exemption_certificate,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('party', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('party', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='party',
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
