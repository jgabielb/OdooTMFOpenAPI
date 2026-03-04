from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.permission'
    _description = 'Permission'
    _inherit = ['tmf.model.mixin']

    creation_date = fields.Datetime(string="creationDate", help="Date when the payment was performed")
    description = fields.Char(string="description", help="Text describing the contents of the payment")
    asset_user_role = fields.Char(string="assetUserRole", help="")
    granter = fields.Char(string="granter", help="")
    privilege = fields.Char(string="privilege", help="")
    user = fields.Char(string="user", help="")
    valid_for = fields.Char(string="validFor", help="The period for which the permission is valid")
    user_partner_id = fields.Many2one("res.partner", string="User Partner", ondelete="set null")
    user_id = fields.Many2one("res.users", string="User", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/permissionManagement/v4/Permission"

    def _safe_json(self, value, default):
        if not value:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    def _resolve_user_partner(self):
        self.ensure_one()
        refs = self._safe_json(self.user, {})
        if isinstance(refs, list) and refs:
            refs = refs[0]
        if not isinstance(refs, dict):
            return False
        env_partner = self.env["res.partner"].sudo()
        rid = refs.get("id")
        if rid:
            partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
            if not partner and str(rid).isdigit():
                partner = env_partner.browse(int(rid))
            if partner and partner.exists():
                return partner
        name = (refs.get("name") or "").strip()
        if name:
            partner = env_partner.search([("name", "=", name)], limit=1)
            if partner:
                return partner
        return False

    def _sync_native_links(self):
        env_users = self.env["res.users"].sudo()
        for rec in self:
            partner = rec._resolve_user_partner()
            if partner:
                rec.user_partner_id = partner.id
                user = env_users.search([("partner_id", "=", partner.id)], limit=1)
                if user:
                    rec.user_id = user.id

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Permission",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "assetUserRole": self.asset_user_role,
            "granter": self.granter,
            "privilege": self.privilege,
            "user": self.user,
            "validFor": self.valid_for,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_native_links()
        for rec in recs:
            self._notify('permission', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "user" in vals or "user_partner_id" in vals or "user_id" in vals:
            self._sync_native_links()
        for rec in self:
            self._notify('permission', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='permission',
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
