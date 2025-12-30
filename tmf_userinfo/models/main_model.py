from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.userinfo'
    _description = 'Userinfo'
    _inherit = ['tmf.model.mixin']

    birthdate = fields.Char(string="birthdate", help="End-User's birthday, represented as an [ISO8601-2004] YYYY-MM-DD format. The year MAY be 0000, indic")
    email = fields.Char(string="email", help="End-User's preferred e-mail address. Its value MUST conform to the [RFC5322] addr-spec syntax")
    emailverified = fields.Boolean(string="email_verified", help="True if the user's email has been verified.")
    familyname = fields.Char(string="family_name", help="Surname(s) or last name(s) of the End-User. Note that in some cultures, people can have multiple fam")
    gender = fields.Char(string="gender", help="End-User's gender. Values defined by this specification are female and male. Other values MAY be use")
    givenname = fields.Char(string="given_name", help="Given name(s) or first name(s) of the End-User. Note that in some cultures, people can have multiple")
    locale = fields.Char(string="locale", help="End-User's locale, represented as a [RFC5646] language tag. This is typically an [ISO639-1] language")
    middlename = fields.Char(string="middle_name", help="Middle name(s) of the End-User. Note that in some cultures, people can have multiple middle names; a")
    name = fields.Char(string="name", help="End-User's full name in displayable form including all name parts, possibly including titles and suf")
    nickname = fields.Char(string="nickname", help="Casual name of the End-User that may or may not be the same as the given_name. For instance, a nickn")
    phonenumber = fields.Char(string="phone_number", help="End-User's preferred telephone number. [E.164] is RECOMMENDED as the format of this Claim, for examp")
    phonenumberverified = fields.Boolean(string="phone_number_verified", help="True if the user's phone number has been verified.")
    picture = fields.Char(string="picture", help="URL of the End-User's profile picture. This URL MUST refer to an image file (for example, a PNG, JPE")
    preferredusername = fields.Char(string="preferred_username", help="Shorthand name by which the End-User wishes to be referred to at the RP, such as janedoe or j.doe. T")
    profile = fields.Char(string="profile", help="URL of the End-User's profile page. The contents of this Web page SHOULD be about the End-User")
    sub = fields.Char(string="sub", help="Subject - Unique Identifier for the End-User")
    website = fields.Char(string="website", help="URL of the End-User's Web page or blog. This Web page SHOULD contain information published by the En")
    zoneinfo = fields.Char(string="zoneinfo", help="String from zoneinfo time zone database representing the End-User's time zone. For example, Europe/P")
    address = fields.Char(string="address", help="Structure including the End-User's preferred postal address")
    legal_id = fields.Char(string="legalId", help="Identification documentation of the contact")
    user_assets = fields.Char(string="userAssets", help="List of additional profile information")

    def _get_tmf_api_path(self):
        return "/userinfoManagement/v4/Userinfo"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Userinfo",
            "birthdate": self.birthdate,
            "email": self.email,
            "email_verified": self.emailverified,
            "family_name": self.familyname,
            "gender": self.gender,
            "given_name": self.givenname,
            "locale": self.locale,
            "middle_name": self.middlename,
            "name": self.name,
            "nickname": self.nickname,
            "phone_number": self.phonenumber,
            "phone_number_verified": self.phonenumberverified,
            "picture": self.picture,
            "preferred_username": self.preferredusername,
            "profile": self.profile,
            "sub": self.sub,
            "website": self.website,
            "zoneinfo": self.zoneinfo,
            "address": self.address,
            "legalId": self.legal_id,
            "userAssets": self.user_assets,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('userinfo', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('userinfo', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='userinfo',
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
