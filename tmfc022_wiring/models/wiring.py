import json
from odoo import api, fields, models


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return None


def _resolve_ids(env, model, items, id_field="tmf_id"):
    """Batch-resolve TMF id references to record IDs for a given model.

    Only uses the TMF id field; no CTK-visible behavior is changed.
    """

    ref_ids = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("id") or "").strip()
        if ref_id:
            ref_ids.append(ref_id)
    if not ref_ids:
        return []
    return env[model].sudo().search([(id_field, "in", ref_ids)]).ids


class PartyPrivacyAgreementTMFC022Wiring(models.Model):
    """TMFC022 wiring for PartyPrivacyAgreement.

    Adds JSON ref fields and relational links to Party and DigitalIdentity in
    a side-car model. Does not change the core TMF payload or controllers.
    """

    _inherit = "tmf.party.privacy.agreement"

    # Wiring-only JSON reference fields. These can be populated by upstream
    # flows without affecting CTK-visible schema.
    engaged_party_json = fields.Text(
        string="engagedParty (JSON Ref)",
        help="Raw TMF engagedParty reference payload used for wiring.",
    )
    privacy_profile_json = fields.Text(
        string="partyPrivacyProfile (JSON Ref)",
        help="Raw TMF partyPrivacyProfile reference payload used for wiring.",
    )

    engaged_partner_ids = fields.Many2many(
        "res.partner",
        "tmfc022_privacy_party_rel",
        "privacy_id",
        "partner_id",
        string="Engaged Parties (TMF632)",
        help="Parties engaged in this privacy agreement.",
    )

    privacy_identity_ids = fields.Many2many(
        "tmf.digital.identity",
        "tmfc022_privacy_identity_rel",
        "privacy_id",
        "identity_id",
        string="Digital Identities",
        help="Digital identities related to this privacy agreement.",
    )

    tmfc022_product_offering_ids = fields.Many2many(
        "product.template",
        "tmfc022_privacy_offering_rel",
        "privacy_id",
        "offering_id",
        string="Product Offerings (TMF620)",
        help="Offerings referenced from the privacy agreement items.",
    )
    tmfc022_document_ids = fields.Many2many(
        "tmf.document",
        "tmfc022_privacy_document_rel",
        "privacy_id",
        "document_id",
        string="Documents (TMF667)",
        help="TMF667 Documents referenced by this privacy agreement.",
    )

    def _resolve_tmf_refs(self):
        """Resolve TMF JSON references into relational links.

        Uses only TMF ids and never mutates TMF payloads or controllers.
        """

        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            # engagedParty → res.partner
            engaged = _loads(rec.engaged_party_json) or []
            if isinstance(engaged, dict):
                engaged = [engaged]
            party_ids = _resolve_ids(self.env, "res.partner", engaged)
            if party_ids:
                updates["engaged_partner_ids"] = [(6, 0, party_ids)]

            # partyPrivacyProfile → tmf.digital.identity (or other domain later)
            profiles = _loads(rec.privacy_profile_json) or []
            if isinstance(profiles, dict):
                profiles = [profiles]
            identity_ids = _resolve_ids(self.env, "tmf.digital.identity", profiles)
            if identity_ids:
                updates["privacy_identity_ids"] = [(6, 0, identity_ids)]

            # agreementItem → TMF620 offering refs / TMF667 document refs
            items = _loads(rec.agreement_item) or []
            if isinstance(items, dict):
                items = [items]
            offering_refs, document_refs = [], []
            for item in items:
                if not isinstance(item, dict):
                    continue
                po = item.get("productOffering") or item.get("offering") or []
                if isinstance(po, dict):
                    po = [po]
                offering_refs.extend(r for r in po if isinstance(r, dict))
                doc = item.get("document") or []
                if isinstance(doc, dict):
                    doc = [doc]
                document_refs.extend(r for r in doc if isinstance(r, dict))
            offering_ids = _resolve_ids(self.env, "product.template", offering_refs)
            if offering_ids:
                updates["tmfc022_product_offering_ids"] = [(6, 0, offering_ids)]
            document_ids = _resolve_ids(self.env, "tmf.document", document_refs)
            if document_ids:
                updates["tmfc022_document_ids"] = [(6, 0, document_ids)]

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
            wiring_keys = {"engaged_party_json", "privacy_profile_json"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res


