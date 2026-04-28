import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TmfCreditRatingCheck(models.Model):
    """TMF645 CreditRatingCheck — a single credit assessment outcome."""

    _name = "tmf.credit.rating.check"
    _description = "TMF645 Credit Rating Check"
    _inherit = ["tmf.model.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Reference", default="New", copy=False)
    partner_id = fields.Many2one("res.partner", string="Party", required=True, ondelete="cascade")

    requested_amount = fields.Float(string="Requested Credit Amount")
    requested_unit = fields.Char(string="Currency Unit", default="USD")

    credit_score = fields.Integer(string="Credit Score")
    credit_rating_result = fields.Selection(
        [("approved", "Approved"), ("rejected", "Rejected"), ("conditional", "Conditional")],
        string="Result",
        default="approved",
    )
    state = fields.Selection(
        [("acknowledged", "Acknowledged"),
         ("inProgress", "In Progress"),
         ("done", "Done"),
         ("rejected", "Rejected")],
        string="State",
        default="done",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "tmf.credit.rating.check"
                ) or "CRC"
        return super().create(vals_list)

    def to_tmf_json(self):
        self.ensure_one()
        partner = self.partner_id
        party_id = getattr(partner, "tmf_id", None) or str(partner.id)
        return {
            "id": self.tmf_id or str(self.id),
            "href": f"/tmf-api/creditManagement/v4/creditRatingCheck/{self.tmf_id or self.id}",
            "@type": "CreditRatingCheck",
            "state": self.state,
            "creditRatingResult": self.credit_rating_result,
            "creditScore": self.credit_score,
            "requestedCreditAmount": {
                "value": self.requested_amount,
                "unit": self.requested_unit or "USD",
            },
            "relatedParty": [{
                "@type": "RelatedParty",
                "id": party_id,
                "name": partner.name,
                "@referredType": "Individual" if partner.company_type == "person" else "Organization",
                "role": "Customer",
            }],
            "creationDate": fields.Datetime.to_string(self.create_date) if self.create_date else None,
        }

    # ------------------------------------------------------------------
    # Scoring policy
    # ------------------------------------------------------------------

    DEFAULT_THRESHOLD = 550

    def _score_partner(self, partner):
        """Stub scoring policy.

        Real deployments would call a scoring service. Defaults: returns the
        partner's last credit_score if set; otherwise generates a deterministic
        score from the partner id so the same party always gets the same score
        within a test session.
        """
        if partner.credit_score:
            return int(partner.credit_score)
        # Deterministic fake score in 600–820, weighted to "approved"
        return 600 + (partner.id * 17 % 220)

    def _evaluate(self, partner, requested_amount):
        """Run the policy and apply side-effects on the partner."""
        score = self._score_partner(partner)
        approved = score >= self.DEFAULT_THRESHOLD
        result = "approved" if approved else "rejected"

        partner.sudo().write({
            "credit_score": score,
            "credit_score_date": fields.Datetime.now(),
            "credit_blocked": (not approved),
        })
        return {"score": score, "result": result}
