from odoo import api, fields, models


class TMFUserinfo(models.Model):
    _name = "tmf.userinfo"
    _description = "TMF691 Userinfo"
    _inherit = ["tmf.model.mixin"]

    birthdate = fields.Char(string="birthdate")
    email = fields.Char(string="email")
    emailverified = fields.Boolean(string="email_verified", default=False)
    familyname = fields.Char(string="family_name")
    gender = fields.Char(string="gender")
    givenname = fields.Char(string="given_name")
    locale = fields.Char(string="locale")
    middlename = fields.Char(string="middle_name")
    name = fields.Char(string="name")
    nickname = fields.Char(string="nickname")
    phonenumber = fields.Char(string="phone_number")
    phonenumberverified = fields.Boolean(string="phone_number_verified", default=False)
    picture = fields.Char(string="picture")
    preferredusername = fields.Char(string="preferred_username")
    profile = fields.Char(string="profile")
    sub = fields.Char(string="sub", required=True, index=True)
    website = fields.Char(string="website")
    zoneinfo = fields.Char(string="zoneinfo")
    address = fields.Json(default=dict)
    legal_id = fields.Json(default=list)
    # Keep legacy storage field for backward compatibility with existing records/views.
    user_assets = fields.Json(default=list)
    user_permission = fields.Json(default=list)
    extra_json = fields.Json(default=dict)

    def _get_tmf_api_path(self):
        return "/federatedIdentity/v5/userinfo"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Userinfo",
            "sub": self.sub,
            "name": self.name or "",
        }
        if self.birthdate:
            payload["birthdate"] = self.birthdate
        if self.email:
            payload["email"] = self.email
        payload["email_verified"] = bool(self.emailverified)
        if self.familyname:
            payload["family_name"] = self.familyname
        if self.gender:
            payload["gender"] = self.gender
        if self.givenname:
            payload["given_name"] = self.givenname
        if self.locale:
            payload["locale"] = self.locale
        if self.middlename:
            payload["middle_name"] = self.middlename
        if self.nickname:
            payload["nickname"] = self.nickname
        if self.phonenumber:
            payload["phone_number"] = self.phonenumber
        payload["phone_number_verified"] = bool(self.phonenumberverified)
        if self.picture:
            payload["picture"] = self.picture
        if self.preferredusername:
            payload["preferred_username"] = self.preferredusername
        if self.profile:
            payload["profile"] = self.profile
        if self.website:
            payload["website"] = self.website
        if self.zoneinfo:
            payload["zoneinfo"] = self.zoneinfo
        if self.address:
            payload["address"] = self.address
        if self.legal_id:
            payload["legalId"] = self.legal_id
        if self.user_permission:
            payload["userPermission"] = self.user_permission
        elif self.user_assets:
            payload["userPermission"] = self.user_assets
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return payload

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("userinfo", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("userinfo", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="userinfo",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
