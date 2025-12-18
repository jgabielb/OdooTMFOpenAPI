from odoo import models, fields, api
import logging
import inspect

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'tmf.model.mixin']

    tmf_status = fields.Selection([
        ('initialized', 'Initialized'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string="TMF Status", default='active')

    tmf_customer_type = fields.Selection([
        ('individual', 'Individual'),
        ('organization', 'Organization'),
    ], string="TMF Party Type")

    def _compute_tmf_type(self):
        self.ensure_one()
        if self.tmf_customer_type:
            return self.tmf_customer_type
        return 'organization' if self.is_company else 'individual'

    def to_tmf_json(self):
        self.ensure_one()
        party_type = self._compute_tmf_type()
        is_individual = party_type == 'individual'

        if is_individual:
            base_path = "/party/v4/individual"
            tmf_type = "Individual"
        else:
            base_path = "/party/v4/organization"
            tmf_type = "Organization"

        tmf_id = self.tmf_id or str(self.id)
        href = f"/tmf-api{base_path}/{tmf_id}"

        data = {"id": tmf_id, "href": href, "@type": tmf_type}

        if is_individual:
            data.update({
                "givenName": self.name,
                "contactMedium": [{
                    "mediumType": "email",
                    "preferred": True,
                    "characteristic": {"emailAddress": self.email},
                }] if self.email else [],
            })
        else:
            data.update({
                "name": self.name,
                "contactMedium": [{
                    "mediumType": "email",
                    "preferred": True,
                    "characteristic": {"emailAddress": self.email},
                }] if self.email else [],
            })

        return data

    def _tmf_party_resource_json(self):
        """Always notify hub with a consistent payload shape."""
        self.ensure_one()
        return {
            "resourceType": "individual" if not self.is_company else "organization",
            "resource": self.to_tmf_json(),
        }

    # ---------- Event hooks for Party /hub ----------

    @api.model
    def create(self, vals):
        rec = super().create(vals)

        if rec.env.context.get("tmf_skip_party_notify"):
            return rec

        rec.env["tmf.hub.subscription"].sudo()._notify_subscribers(
            api_name="party",
            event_type="create",
            resource_json=rec._tmf_party_resource_json(),
        )
        return rec

    def write(self, vals):
        # prevent re-entrance / duplicate notifications
        if self.env.context.get("tmf_party_notified"):
            return super().write(vals)

        res = super().write(vals)

        if self.env.context.get("tmf_skip_party_notify"):
            return res

        # only notify when relevant fields change
        if not any(k in vals for k in ("name", "email", "phone", "mobile")):
            return res

        for rec in self:
            rec.with_context(tmf_party_notified=True).env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name="party",              # ✅ IMPORTANT
                event_type="update",           # ✅ aligned with your subs filter
                resource_json=rec._tmf_party_resource_json(),
            )

        return res

    def unlink(self):
        # capture before delete
        payloads = [p._tmf_party_resource_json() for p in self]

        # ✅ skip if coming from a flow where we don't want party notifications
        if self.env.context.get("tmf_skip_party_notify"):
            return super().unlink()

        res = super().unlink()

        for payload in payloads:
            try:
                self.env['tmf.hub.subscription'].sudo()._notify_subscribers(
                    api_name='party',
                    event_type='delete',            # ✅ aligned with subscriptions
                    resource_json=payload,
                )
            except Exception:
                continue

        return res

    def _get_tmf_api_path(self):
        self.ensure_one()
        return "/party/v4/organization" if self.is_company else "/party/v4/individual"
