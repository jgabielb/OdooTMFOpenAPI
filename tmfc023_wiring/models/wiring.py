import json
from odoo import api, fields, models


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return None


def _as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    return []


class PartyInteractionTMFC023Wiring(models.Model):
    """TMFC023 wiring for PartyInteraction (TMF683).

    Adds relational links into DigitalIdentity and PrivacyAgreement models in a
    side-car; does not alter TMF683 controller or payload behavior.
    """

    _inherit = "tmf.party.interaction"

    digital_identity_ids = fields.Many2many(
        "tmf.digital.identity",
        "tmfc023_interaction_identity_rel",
        "interaction_id",
        "identity_id",
        string="Related Digital Identities",
        help="Digital identities related to this interaction.",
    )

    privacy_agreement_ids = fields.Many2many(
        "tmf.party.privacy.agreement",
        "tmfc023_interaction_privacy_rel",
        "interaction_id",
        "agreement_id",
        string="Related Privacy Agreements",
        help="Privacy agreements referenced by this interaction.",
    )

    tmfc023_document_ids = fields.Many2many(
        "tmf.document", "tmfc023_interaction_document_rel",
        "interaction_id", "document_id", string="Documents (TMF667)",
        help="TMF667 Documents referenced by interaction items/attachments.",
    )
    tmfc023_communication_message_ids = fields.Many2many(
        "tmf.communication.message", "tmfc023_interaction_message_rel",
        "interaction_id", "message_id", string="Communication Messages (TMF681)",
        help="TMF681 CommunicationMessages related to this interaction.",
    )
    tmfc023_entity_specification_ids = fields.Many2many(
        "tmf.entity.specification", "tmfc023_interaction_entity_spec_rel",
        "interaction_id", "entity_spec_id", string="Entity Specifications (TMF662)",
        help="TMF662 EntitySpecifications describing this interaction's items.",
    )

    def _resolve_tmf_refs(self):
        """Resolve DigitalIdentity / PrivacyAgreement refs from related_party.

        TMF683 carries related entities inside ``related_party`` with a
        ``@referredType`` discriminator; we extract the identity and
        privacy-agreement entries and resolve them by ``tmf_id``. This is
        idempotent and never alters CTK-visible behavior.
        """

        Identity = self.env["tmf.digital.identity"].sudo()
        Agreement = self.env["tmf.party.privacy.agreement"].sudo()
        ctx = {"skip_tmf_wiring": True}

        for rec in self:
            items = _as_list(rec.related_party)
            identity_refs = [
                i for i in items
                if isinstance(i, dict)
                and (i.get("@referredType") == "DigitalIdentity"
                     or i.get("@type") in ("DigitalIdentityRef",))
            ]
            agreement_refs = [
                i for i in items
                if isinstance(i, dict)
                and (i.get("@referredType") == "PartyPrivacyAgreement"
                     or i.get("@type") in ("PartyPrivacyAgreementRef",))
            ]

            updates = {}

            ident_ids = []
            for ref in identity_refs:
                rid = str(ref.get("id") or "").strip()
                if not rid:
                    continue
                hit = Identity.search([("tmf_id", "=", rid)], limit=1)
                if not hit and rid.isdigit():
                    hit = Identity.browse(int(rid))
                    if not hit.exists():
                        hit = Identity.browse([])
                if hit:
                    ident_ids.append(hit.id)
            if ident_ids:
                updates["digital_identity_ids"] = [(6, 0, ident_ids)]

            agr_ids = []
            for ref in agreement_refs:
                rid = str(ref.get("id") or "").strip()
                if not rid:
                    continue
                hit = Agreement.search([("tmf_id", "=", rid)], limit=1)
                if not hit and rid.isdigit():
                    hit = Agreement.browse(int(rid))
                    if not hit.exists():
                        hit = Agreement.browse([])
                if hit:
                    agr_ids.append(hit.id)
            if agr_ids:
                updates["privacy_agreement_ids"] = [(6, 0, agr_ids)]

            # TMF667 documents / TMF681 messages / TMF662 entity specs are
            # referenced from interaction items and attachments by @referredType
            item_refs = []
            for attr in ("interaction_item", "interaction_item_json", "attachment"):
                if attr in rec._fields:
                    item_refs.extend(_as_list(_loads(rec[attr])))
            item_refs.extend(items)

            def _collect(referred_types, model):
                ids = []
                Model = self.env[model].sudo()
                for ref in item_refs:
                    if not isinstance(ref, dict):
                        continue
                    inner = ref.get("item") if isinstance(ref.get("item"), dict) else ref
                    if (inner.get("@referredType") or inner.get("@type")) not in referred_types:
                        continue
                    rid = str(inner.get("id") or "").strip()
                    if not rid:
                        continue
                    hit = Model.search([("tmf_id", "=", rid)], limit=1)
                    if hit:
                        ids.append(hit.id)
                return ids

            doc_ids = _collect(("Document", "DocumentRef"), "tmf.document")
            if doc_ids:
                updates["tmfc023_document_ids"] = [(6, 0, doc_ids)]
            msg_ids = _collect(("CommunicationMessage", "CommunicationMessageRef"),
                               "tmf.communication.message")
            if msg_ids:
                updates["tmfc023_communication_message_ids"] = [(6, 0, msg_ids)]
            spec_ids = _collect(("EntitySpecification", "EntitySpecificationRef"),
                                "tmf.entity.specification")
            if spec_ids:
                updates["tmfc023_entity_specification_ids"] = [(6, 0, spec_ids)]

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            self._resolve_tmf_refs()
        return res


