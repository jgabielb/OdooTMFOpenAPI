from odoo import api, fields, models


class TMFUserinfo(models.Model):
    _name = "tmf.userinfo"
    _description = "TMF691 Userinfo"
    _inherit = ["tmf.model.mixin"]

    birthdate = fields.Char(string="Birth Date")
    email = fields.Char(string="Email")
    emailverified = fields.Boolean(string="Email Verified", default=False)
    familyname = fields.Char(string="Family Name")
    gender = fields.Char(string="gender")
    givenname = fields.Char(string="Given Name")
    locale = fields.Char(string="locale")
    middlename = fields.Char(string="Middle Name")
    name = fields.Char(string="name")
    nickname = fields.Char(string="nickname")
    phonenumber = fields.Char(string="Phone Number")
    phonenumberverified = fields.Boolean(string="Phone Number Verified", default=False)
    picture = fields.Char(string="picture")
    preferredusername = fields.Char(string="Preferred Username")
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
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    user_id = fields.Many2one("res.users", string="User", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/federatedIdentity/v5/userinfo"

    def _sync_native_links(self):
        env_partner = self.env["res.partner"].sudo()
        env_users = self.env["res.users"].sudo()
        for rec in self:
            partner = False
            if rec.sub:
                partner = env_partner.search([("tmf_id", "=", rec.sub)], limit=1)
            if not partner and rec.email:
                partner = env_partner.search([("email", "=", rec.email)], limit=1)
            if not partner and rec.name:
                partner = env_partner.search([("name", "=", rec.name)], limit=1)
            if partner:
                rec.partner_id = partner.id
                user = env_users.search([("partner_id", "=", partner.id)], limit=1)
                if user:
                    rec.user_id = user.id

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
        recs._sync_native_links()
        for rec in recs:
            self._notify("userinfo", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "sub" in vals or "email" in vals or "name" in vals or "partner_id" in vals or "user_id" in vals:
            self._sync_native_links()
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
