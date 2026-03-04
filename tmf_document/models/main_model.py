# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json


def _dumps(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else False


def _loads(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _iso(dt):
    # Keep it simple and predictable. Odoo stores UTC in DB; isoformat is fine for TMF usage.
    return dt.isoformat() if dt else None


class TMFDocument(models.Model):
    _name = "tmf.document"
    _description = "TMF667 Document"
    _inherit = ["tmf.model.mixin"]

    # Spec fields
    creation_date = fields.Datetime(string="creationDate")
    last_update = fields.Datetime(string="lastUpdate")
    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    document_type = fields.Char(string="documentType")
    version = fields.Char(string="version")

    # TMF667 uses "status" for Document lifecycle (DocumentStatusType)
    status = fields.Char(string="status")

    # Complex fields (store JSON)
    attachment_json = fields.Text(string="attachment")               # AttachmentRefOrValue[*]
    category_json = fields.Text(string="category")                   # CategoryRef[*]
    characteristic_json = fields.Text(string="characteristic")       # Characteristic[*]
    document_json = fields.Text(string="document")                   # DocumentRef[*]
    document_specification_json = fields.Text(string="documentSpecification")  # DocumentSpecificationRefOrValue
    external_identifier_json = fields.Text(string="externalIdentifier")        # ExternalIdentifier[*]
    related_entity_json = fields.Text(string="relatedEntity")         # RelatedEntity[*]
    related_party_json = fields.Text(string="relatedParty")           # RelatedParty[*]
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")

    def _get_tmf_api_path(self):
        # Controller exposes /tmf-api/document/v4/document
        return "/document/v4/document"

    # ---------- TMF serialization ----------
    def to_tmf_json(self, fields=None):
        self.ensure_one()
        obj = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Document",
            "creationDate": _iso(self.creation_date),
            "lastUpdate": _iso(self.last_update),
            "name": self.name,
            "description": self.description,
            "documentType": self.document_type,
            "version": self.version,
            "status": self.status,
            "attachment": _loads(self.attachment_json) or None,
            "category": _loads(self.category_json) or None,
            "characteristic": _loads(self.characteristic_json) or None,
            "document": _loads(self.document_json) or None,
            "documentSpecification": _loads(self.document_specification_json) or None,
            "externalIdentifier": _loads(self.external_identifier_json) or None,
            "relatedEntity": _loads(self.related_entity_json) or None,
            "relatedParty": _loads(self.related_party_json) or None,
        }

        # TMF "fields=" selection: only first-level attributes
        if fields:
            keep = set(fields) | {"id", "href"}  # id/href are commonly expected, but keep as requested if present
            return {k: v for k, v in obj.items() if k in keep}
        return obj

    # ---------- TMF deserialization ----------
    def from_tmf_json(self, data, partial=False):
        """
        Map TMF JSON -> Odoo create/write vals.
        partial=True means PATCH merge-patch; we only map present keys.
        """
        vals = {}

        def set_if_present(src_key, dst_key, transform=lambda x: x):
            if src_key in data:
                vals[dst_key] = transform(data.get(src_key))

        # Non-patchable handled in controller (id/href)
        set_if_present("creationDate", "creation_date")
        set_if_present("lastUpdate", "last_update")
        set_if_present("name", "name", lambda x: (x or "").strip())
        set_if_present("description", "description")
        set_if_present("documentType", "document_type")
        set_if_present("version", "version")
        set_if_present("status", "status")

        # Complex structures
        set_if_present("attachment", "attachment_json", _dumps)
        set_if_present("category", "category_json", _dumps)
        set_if_present("characteristic", "characteristic_json", _dumps)
        set_if_present("document", "document_json", _dumps)
        set_if_present("documentSpecification", "document_specification_json", _dumps)
        set_if_present("externalIdentifier", "external_identifier_json", _dumps)
        set_if_present("relatedEntity", "related_entity_json", _dumps)
        set_if_present("relatedParty", "related_party_json", _dumps)

        # Mandatory on POST: name
        if not partial and not vals.get("name"):
            raise ValueError("TMF667 POST: 'name' is mandatory")

        return vals

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        parties = _loads(self.related_party_json) or []
        if not isinstance(parties, list):
            parties = [parties] if parties else []
        env = self.env["res.partner"].sudo()
        for party in parties:
            if not isinstance(party, dict):
                continue
            rid = party.get("id")
            if rid:
                partner = env.search([("tmf_id", "=", str(rid))], limit=1)
                if partner:
                    return partner
                if str(rid).isdigit():
                    partner = env.browse(int(rid))
                    if partner.exists():
                        return partner
            name = (party.get("name") or "").strip()
            if name:
                partner = env.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _sync_partner_link(self):
        for rec in self:
            partner = rec._resolve_partner_from_related_party()
            if partner:
                rec.partner_id = partner.id

    # ---------- Notifications (aligned event names) ----------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_partner_link()
        for rec in recs:
            rec._notify("DocumentCreateEvent")
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "related_party_json" in vals or "partner_id" in vals:
            self._sync_partner_link()
        for rec in self:
            rec._notify("DocumentChangeEvent")
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="document",
                    event_type="DocumentDeleteEvent",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, event_type):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="document",
                event_type=event_type,
                resource_json=self.to_tmf_json(),
            )
        except Exception:
            pass
