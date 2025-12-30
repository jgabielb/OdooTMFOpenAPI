from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.geographic.address'
    _description = 'GeographicAddress'
    _inherit = ['tmf.model.mixin']

    city = fields.Char(string="city", help="City that the address is in")
    country = fields.Char(string="country", help="Country that the address is in")
    locality = fields.Char(string="locality", help="An area of defined or undefined boundaries within a local authority or other legislatively defined a")
    name = fields.Char(string="name", help="A user-friendly name for the place, such as [Paris Store], [London Store], [Main Home]")
    postcode = fields.Char(string="postcode", help="descriptor for a postal delivery area, used to speed and simplify the delivery of mail (also know as")
    state_or_province = fields.Char(string="stateOrProvince", help="the State or Province that the address is in")
    street_name = fields.Char(string="streetName", help="Name of the street or other street type")
    street_nr = fields.Char(string="streetNr", help="Number identifying a specific property on a public street. It may be combined with streetNrLast for ")
    street_nr_last = fields.Char(string="streetNrLast", help="Last number in a range of street numbers allocated to a property")
    street_nr_last_suffix = fields.Char(string="streetNrLastSuffix", help="Last street number suffix for a ranged address")
    street_nr_suffix = fields.Char(string="streetNrSuffix", help="the first street number suffix")
    street_suffix = fields.Char(string="streetSuffix", help="A modifier denoting a relative direction")
    street_type = fields.Char(string="streetType", help="alley, avenue, boulevard, brae, crescent, drive, highway, lane, terrace, parade, place, tarn, way, w")
    geographic_location = fields.Char(string="geographicLocation", help="")
    geographic_sub_address = fields.Char(string="geographicSubAddress", help="")
    geographic_address_id = fields.Many2one(
        'tmf.geographic.address', 
        string="Linked Address",
        help="The physical address of this site"
    )

    def _get_tmf_api_path(self):
        return "/geographic_addressManagement/v4/GeographicAddress"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "GeographicAddress",
            "city": self.city,
            "country": self.country,
            "locality": self.locality,
            "name": self.name,
            "postcode": self.postcode,
            "stateOrProvince": self.state_or_province,
            "streetName": self.street_name,
            "streetNr": self.street_nr,
            "streetNrLast": self.street_nr_last,
            "streetNrLastSuffix": self.street_nr_last_suffix,
            "streetNrSuffix": self.street_nr_suffix,
            "streetSuffix": self.street_suffix,
            "streetType": self.street_type,
            "geographicLocation": self.geographic_location,
            "geographicSubAddress": self.geographic_sub_address,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('geographicAddress', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('geographicAddress', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='geographicAddress',
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
