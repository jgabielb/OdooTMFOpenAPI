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
    """Batch-search model by tmf_id for all item dicts. Returns list of record IDs."""
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


class DigitalIdentityTMFC020Wiring(models.Model):
    """TMFC020 dependent API wiring for DigitalIdentity (tmf.digital.identity)."""
    _inherit = "tmf.digital.identity"

    # Resolved relational fields
    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc020_identity_partner_rel",
        "identity_id", "partner_id", string="Related Parties (TMF632)"
    )
    individual_partner_id = fields.Many2one(
        "res.partner", string="Individual Identified (TMF632)",
        index=True, ondelete="set null"
    )
    party_role_ids = fields.Many2many(
        "tmf.party.role", "tmfc020_identity_party_role_rel",
        "identity_id", "role_id", string="Party Roles (TMF669)"
    )
    resource_ids = fields.Many2many(
        "stock.lot", "tmfc020_identity_resource_rel",
        "identity_id", "lot_id", string="Resources Identified (TMF639)"
    )

    def _resolve_tmf_refs(self):
        """Resolve TMF JSON reference IDs to local Odoo records."""
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            # TMF632 relatedParty → res.partner (exclude PartyRole entries)
            if not rec.related_partner_ids and rec.related_party_json:
                items = _loads(rec.related_party_json) or []
                items = [i for i in items
                         if isinstance(i, dict) and i.get("@type") not in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "res.partner", items)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            # TMF669 partyRoleIdentified → tmf.party.role
            if not rec.party_role_ids:
                items = _loads(rec.party_role_identified_json) or []
                if isinstance(items, dict):
                    items = [items]
                # also pick PartyRole entries from relatedParty
                related = _loads(rec.related_party_json) or []
                role_items = [i for i in related
                              if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items + role_items)
                if ids:
                    updates["party_role_ids"] = [(6, 0, ids)]

            # TMF632 individualIdentified → res.partner (single ref)
            if not rec.individual_partner_id and rec.individual_identified_json:
                ref = _loads(rec.individual_identified_json)
                if isinstance(ref, dict):
                    ref_id = str(ref.get("id") or "").strip()
                    if ref_id:
                        partner = self.env["res.partner"].sudo().search(
                            [("tmf_id", "=", ref_id)], limit=1
                        )
                        if partner:
                            updates["individual_partner_id"] = partner.id

            # TMF639 resourceIdentified → stock.lot
            if not rec.resource_ids and rec.resource_identified_json:
                items = _loads(rec.resource_identified_json) or []
                if isinstance(items, dict):
                    items = [items]
                ids = _resolve_ids(self.env, "stock.lot", items)
                if ids:
                    updates["resource_ids"] = [(6, 0, ids)]

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
            wiring_keys = {
                "related_party_json", "individual_identified_json",
                "party_role_identified_json", "resource_identified_json",
            }
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res
