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

    _TMFC031_WIRING_KEYS = frozenset((
        "related_party_json", "product_json", "usage_json", "payload", "tmf_id",
    ))

    def _resolve_tmf_refs(self, changed_keys=None):
        """Rebuild relational links from raw TMF JSON refs (JSON is source of truth)."""
        ctx = {"skip_tmf_wiring": True}
        explicit = changed_keys or set()
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

            def _rebuild(field_name, model, items, triggered):
                if not items and not triggered:
                    return
                ids = _resolve_ids(self.env, model, items)
                if set(ids) != set(rec[field_name].ids):
                    updates[field_name] = [(6, 0, ids)]

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

            _rebuild("related_partner_ids", "res.partner", effective_party_json,
                     bool(explicit & {"related_party_json", "payload"}))
            _rebuild("product_ids", "tmf.product", effective_product_json,
                     bool(explicit & {"product_json", "payload"}))
            _rebuild("usage_ids", "tmf.usage", effective_usage_json,
                     bool(explicit & {"usage_json", "payload"}))

            # TMF669 partyRole — first match from relatedParty with PartyRole @type
            role_items = [i for i in effective_party_json
                          if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
            role_ids = _resolve_ids(self.env, "tmf.party.role", role_items)
            if role_ids and rec.party_role_id.id != role_ids[0]:
                updates["party_role_id"] = role_ids[0]
            elif not role_items and explicit & {"related_party_json", "payload"} and rec.party_role_id:
                updates["party_role_id"] = False

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
            changed = self._TMFC031_WIRING_KEYS & set(vals.keys())
            if changed:
                self._resolve_tmf_refs(changed_keys=changed)
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

    _TMFC031_RATE_KEYS = frozenset(("related_party_json", "product_json", "payload"))

    def _resolve_tmf_refs(self, changed_keys=None):
        ctx = {"skip_tmf_wiring": True}
        explicit = changed_keys or set()
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

            def _rebuild(field_name, model, items, triggered):
                if not items and not triggered:
                    return
                ids = _resolve_ids(self.env, model, items)
                if set(ids) != set(rec[field_name].ids):
                    updates[field_name] = [(6, 0, ids)]

            _rebuild("related_partner_ids", "res.partner", rec.related_party_json,
                     "related_party_json" in explicit)
            _rebuild("product_ids", "tmf.product", rec.product_json,
                     "product_json" in explicit)

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
            changed = self._TMFC031_RATE_KEYS & set(vals.keys())
            if changed:
                self._resolve_tmf_refs(changed_keys=changed)
        return res
