from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.managed.entity'
    _description = 'ManagedEntity'
    _inherit = ['tmf.model.mixin']

    context = fields.Char(string="context", help="A string used to give a context to the entity")
    description = fields.Char(string="description", help="free-text description of the entity")
    valid_for = fields.Char(string="validFor", help="The period for which this REST resource is valid")
    is_bundle = fields.Boolean(string="isBundle", help="isBundle determines whether an entity represents a single entity (false), or a bundle of entities(tr")
    is_external = fields.Boolean(string="isExternal", help="isExternal determines whether an entity represents an external entity in the inventory.")
    name = fields.Char(string="name", help="A string used to give a name to the entity")
    last_update = fields.Datetime(string="lastUpdate", help="Date and time of the last update of this REST resource")
    lifecycle_status = fields.Char(string="lifecycleStatus", help="Used to indicate the current lifecycle status of this managed entity")
    status_change_date = fields.Datetime(string="statusChangeDate", help="A date time( DateTime). The date that the entity status changed")
    version = fields.Char(string="version", help="A field that identifies the specific version of an instance of an entity.")
    attachment = fields.Char(string="attachment", help="Attachments that may be of relevance to this entity, such as picture, document, media")
    characteristic = fields.Char(string="characteristic", help="")
    entity_relationship = fields.Char(string="entityRelationship", help="A list of entities related to this entity")
    entity_specification = fields.Char(string="entitySpecification", help="")
    note = fields.Char(string="note", help="")
    related_party = fields.Char(string="relatedParty", help="")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")

    def _get_tmf_api_path(self):
        return "/managed_entityManagement/v4/ManagedEntity"

    def _safe_json(self, value, default):
        if not value:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    def _resolve_partner(self):
        self.ensure_one()
        refs = self._safe_json(self.related_party, [])
        if isinstance(refs, dict):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        env_partner = self.env["res.partner"].sudo()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (ref.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _resolve_product_template(self):
        self.ensure_one()
        env_pt = self.env["product.template"].sudo()
        if self.tmf_id:
            pt = env_pt.search([("tmf_id", "=", self.tmf_id)], limit=1)
            if pt:
                return pt
        if self.name:
            pt = env_pt.search([("name", "=", self.name)], limit=1)
            if pt:
                return pt
        return False

    def _sync_native_links(self):
        for rec in self:
            partner = rec._resolve_partner()
            if partner:
                rec.partner_id = partner.id
            pt = rec._resolve_product_template()
            if pt:
                rec.product_tmpl_id = pt.id

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ManagedEntity",
            "context": self.context,
            "description": self.description,
            "validFor": self.valid_for,
            "isBundle": self.is_bundle,
            "isExternal": self.is_external,
            "name": self.name,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status,
            "statusChangeDate": self.status_change_date.isoformat() if self.status_change_date else None,
            "version": self.version,
            "attachment": self.attachment,
            "characteristic": self.characteristic,
            "entityRelationship": self.entity_relationship,
            "entitySpecification": self.entity_specification,
            "note": self.note,
            "relatedParty": self.related_party,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_native_links()
        for rec in recs:
            self._notify('managedEntity', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "related_party" in vals or "name" in vals or "partner_id" in vals or "product_tmpl_id" in vals:
            self._sync_native_links()
        for rec in self:
            self._notify('managedEntity', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='managedEntity',
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
