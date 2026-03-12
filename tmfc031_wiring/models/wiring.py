from odoo import api, fields, models


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


class CustomerBillTMFC031Wiring(models.Model):
    """TMFC031 dependent API wiring for CustomerBill (tmf.customer.bill)."""
    _inherit = "tmf.customer.bill"

    # Raw JSON storage for cross-API refs
    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_json = fields.Json(default=list, string="Product refs JSON (TMF637)")
    usage_json = fields.Json(default=list, string="Usage refs JSON (TMF635)")

    # Resolved relational fields
    billing_account_id = fields.Many2one(
        "tmf.billing.account", string="Billing Account (TMF666)",
        index=True, ondelete="set null"
    )
    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc031_bill_partner_rel",
        "bill_id", "partner_id", string="Related Parties (TMF632)"
    )
    product_ids = fields.Many2many(
        "tmf.product", "tmfc031_bill_product_rel",
        "bill_id", "product_id", string="Products (TMF637)"
    )
    usage_ids = fields.Many2many(
        "tmf.usage", "tmfc031_bill_usage_rel",
        "bill_id", "usage_id", string="Usage Records (TMF635)"
    )
    party_role_id = fields.Many2one(
        "tmf.party.role", string="Party Role (TMF669)",
        index=True, ondelete="set null"
    )
    process_flow_id = fields.Many2one(
        "tmf.process.flow", string="Process Flow (TMF701)",
        index=True, ondelete="set null"
    )

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}
            payload = rec.payload or {}

            # Supplement dedicated JSON fields from payload when controller didn't populate them.
            # The verify script sends productRef; the controller stores it only in payload.
            effective_party_json = rec.related_party_json or payload.get("relatedParty") or []
            effective_product_json = (
                rec.product_json
                or payload.get("productRef")       # verify_wiring.py sends productRef
                or payload.get("product")           # alternative key used by some callers
                or []
            )
            effective_usage_json = rec.usage_json or payload.get("usage") or []

            # TMF666 billingAccount — from payload
            if not rec.billing_account_id:
                ba = payload.get("billingAccount") or {}
                ba_id = str(ba.get("id") or "").strip()
                if ba_id:
                    match = self.env["tmf.billing.account"].sudo().search(
                        [("tmf_id", "=", ba_id)], limit=1
                    )
                    if match:
                        updates["billing_account_id"] = match.id

            # TMF632 relatedParty → res.partner
            if not rec.related_partner_ids and effective_party_json:
                ids = _resolve_ids(self.env, "res.partner", effective_party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            # TMF637 product → tmf.product
            if not rec.product_ids and effective_product_json:
                ids = _resolve_ids(self.env, "tmf.product", effective_product_json)
                if ids:
                    updates["product_ids"] = [(6, 0, ids)]

            # TMF635 usage → tmf.usage
            if not rec.usage_ids and effective_usage_json:
                ids = _resolve_ids(self.env, "tmf.usage", effective_usage_json)
                if ids:
                    updates["usage_ids"] = [(6, 0, ids)]

            # TMF669 partyRole — first match from relatedParty with PartyRole @type
            if not rec.party_role_id and effective_party_json:
                items = [i for i in effective_party_json
                         if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["party_role_id"] = ids[0]

            # TMF701 processFlow — from payload
            if not rec.process_flow_id:
                pf = payload.get("processFlow") or {}
                pf_id = str(pf.get("id") or "").strip()
                if pf_id:
                    match = self.env["tmf.process.flow"].sudo().search(
                        [("tmf_id", "=", pf_id)], limit=1
                    )
                    if match:
                        updates["process_flow_id"] = match.id

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
            wiring_keys = {"related_party_json", "product_json", "usage_json", "payload", "tmf_id"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res


class AppliedBillingRateTMFC031Wiring(models.Model):
    """TMFC031 dependent API wiring for AppliedCustomerBillingRate."""
    _inherit = "tmf.applied.customer.billing.rate"

    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_json = fields.Json(default=list, string="Product refs JSON (TMF637)")

    billing_account_id = fields.Many2one(
        "tmf.billing.account", string="Billing Account (TMF666)",
        index=True, ondelete="set null"
    )
    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc031_rate_partner_rel",
        "rate_id", "partner_id", string="Related Parties (TMF632)"
    )
    product_ids = fields.Many2many(
        "tmf.product", "tmfc031_rate_product_rel",
        "rate_id", "product_id", string="Products (TMF637)"
    )

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            if not rec.billing_account_id:
                payload = rec.payload or {}
                ba = payload.get("billingAccount") or {}
                ba_id = str(ba.get("id") or "").strip()
                if ba_id:
                    match = self.env["tmf.billing.account"].sudo().search(
                        [("tmf_id", "=", ba_id)], limit=1
                    )
                    if match:
                        updates["billing_account_id"] = match.id

            if not rec.related_partner_ids and rec.related_party_json:
                ids = _resolve_ids(self.env, "res.partner", rec.related_party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            if not rec.product_ids and rec.product_json:
                ids = _resolve_ids(self.env, "tmf.product", rec.product_json)
                if ids:
                    updates["product_ids"] = [(6, 0, ids)]

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
            wiring_keys = {"related_party_json", "product_json", "payload"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res
