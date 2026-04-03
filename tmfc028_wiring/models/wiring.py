from odoo import models, fields


class PartyTMFC028Wiring(models.Model):
    """TMFC028 wiring for Party (TMF632) into related domains.

    Pure side-car addon: no controller changes, no CTK-visible behavior changes.
    """

    _inherit = "res.partner"

    digital_identity_ids = fields.One2many(
        "tmf.digital.identity",
        "partner_id",
        string="Digital Identities (TMF720)",
        help="Digital identities linked to this party via TMF720.",
    )

    privacy_agreement_ids = fields.Many2many(
        "tmf.party.privacy.agreement",
        "tmfc028_party_privacy_rel",
        "partner_id",
        "agreement_id",
        string="Privacy Agreements",
        help="Party privacy agreements this party is engaged in.",
    )

    party_interaction_ids = fields.One2many(
        "tmf.party.interaction",
        "partner_id",
        string="Party Interactions (TMF683)",
        help="Party interactions associated with this party.",
    )


