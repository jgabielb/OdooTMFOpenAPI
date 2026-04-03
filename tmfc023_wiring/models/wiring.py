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

    def _resolve_tmf_refs(self):
        """Placeholder for future TMF-based reference resolution.

        Current TMF683 implementation does not expose explicit identity or
        privacy agreement refs; this hook allows safe future wiring once such
        fields are introduced, without touching CTK-facing behavior.
        """

        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            # Future extension point: e.g., resolve relatedEntity/relatedParty
            # entries into digital_identity_ids / privacy_agreement_ids.
            # For now, we keep this as a no-op to avoid changing behavior.

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


