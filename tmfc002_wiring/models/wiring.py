import json

from odoo import api, fields, models


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return None


def _as_list(value):
    value = _loads(value)
    if isinstance(value, dict):
        return [value]
    return value if isinstance(value, list) else []


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


PARTY_ROLE_TYPES = ("PartyRole", "PartyRoleRef")


class ProductOrderTMFC002Wiring(models.Model):
    """TMFC002 dependent API wiring for ProductOrder (TMF622)."""

    _inherit = "sale.order"

    # Raw TMF reference payload fragments (stored by TMF622 controller)
    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_offering_json = fields.Json(default=list, string="ProductOffering refs JSON (TMF620)")
    billing_account_json = fields.Json(default=dict, string="BillingAccount JSON (TMF666)")

    # Resolved relations (ODA/TMFC002 view)
    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc002_order_partner_rel",
        "order_id", "partner_id", string="Related Parties (TMF632)",
    )
    product_offering_ids = fields.Many2many(
        "product.template", "tmfc002_order_offering_rel",
        "order_id", "offering_id", string="Product Offerings (TMF620)",
    )
    billing_account_id = fields.Many2one(
        "tmf.billing.account", string="Billing Account (TMF666)",
        index=True, ondelete="set null",
    )

    # Pre-order / qualification context (optional but useful for TMFC002)
    poq_ids = fields.Many2many(
        "tmf.check.product.offering.qualification", "tmfc002_order_poq_rel",
        "order_id", "poq_id", string="Check POQ (TMF679)",
    )
    sq_ids = fields.Many2many(
        "tmf.service.qualification", "tmfc002_order_sq_rel",
        "order_id", "sq_id", string="Service Qualifications (TMF645)",
    )
    cart_ids = fields.Many2many(
        "tmf.shopping.cart", "tmfc002_order_cart_rel",
        "order_id", "cart_id", string="Shopping Carts (TMF663)",
    )

    # Kept for compatibility; ProductOrder is implemented directly on sale.order.
    sale_order_id = fields.Many2one(
        "sale.order", string="Linked Odoo Sales Order",
        index=True, ondelete="set null",
    )

    _TMFC002_WIRING_KEYS = frozenset((
        "related_party_json", "product_offering_json", "billing_account_json", "payload",
    ))

    def _resolve_tmf_refs(self, changed_keys=None):
        """Rebuild ODA relational links from raw TMF JSON refs.

        JSON refs (side-car fields or the stored TMF payload) are the source of
        truth: explicitly rewritten refs rebuild the relations even when that
        clears them; otherwise empty refs leave existing links untouched.
        """
        ctx = {"skip_tmf_wiring": True}
        explicit = changed_keys or set()
        for rec in self:
            updates = {}
            payload = _loads(getattr(rec, "payload", None)) or {}

            def _rebuild(field_name, model, items, triggered):
                if not items and not triggered:
                    return
                ids = _resolve_ids(self.env, model, items)
                if set(ids) != set(rec[field_name].ids):
                    updates[field_name] = [(6, 0, ids)]

            # TMF632 relatedParty -> res.partner
            party_json = rec.related_party_json or payload.get("relatedParty") or []
            _rebuild("related_partner_ids", "res.partner", party_json,
                     bool(explicit & {"related_party_json", "payload"}))

            # TMF620 productOffering -> product.template
            po_json = list(rec.product_offering_json or [])
            if not po_json:
                for item in (payload.get("productOrderItem") or payload.get("orderItem") or []):
                    if not isinstance(item, dict):
                        continue
                    po = item.get("productOffering") or {}
                    if isinstance(po, dict) and po.get("id"):
                        po_json.append(po)
            _rebuild("product_offering_ids", "product.template", po_json,
                     bool(explicit & {"product_offering_json", "payload"}))

            # TMF666 billingAccount -> tmf.billing.account
            ba = rec.billing_account_json or payload.get("billingAccount") or {}
            if isinstance(ba, list):
                ba = ba[0] if ba else {}
            ba_id = str((ba or {}).get("id") or "").strip() if isinstance(ba, dict) else ""
            if ba_id:
                match = self.env["tmf.billing.account"].sudo().search(
                    [("tmf_id", "=", ba_id)], limit=1)
                if match and rec.billing_account_id.id != match.id:
                    updates["billing_account_id"] = match.id
            elif explicit & {"billing_account_json", "payload"} and rec.billing_account_id:
                updates["billing_account_id"] = False

            # Pre-order / qualification context linking from the stored payload
            _rebuild("poq_ids", "tmf.check.product.offering.qualification",
                     _as_list(payload.get("productOfferingQualification")),
                     "payload" in explicit)
            _rebuild("sq_ids", "tmf.service.qualification",
                     _as_list(payload.get("serviceQualification")),
                     "payload" in explicit)
            _rebuild("cart_ids", "tmf.shopping.cart",
                     _as_list(payload.get("shoppingCart")),
                     "payload" in explicit)

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
            changed = self._TMFC002_WIRING_KEYS & set(vals.keys())
            if changed:
                self._resolve_tmf_refs(changed_keys=changed)
        return res


class QuoteTMFC002Wiring(models.Model):
    """TMFC002 dependent API wiring for Quote (TMF648, exposed resource).

    The base ``tmf.quote`` model already stores the raw TMF ref fragments
    (Text JSON fields + quote items); this extension resolves them into
    relational links by ``tmf_id``.
    """

    _inherit = "tmf.quote"

    tmfc002_related_partner_ids = fields.Many2many(
        "res.partner", "tmfc002_quote_partner_rel",
        "quote_id", "partner_id", string="Related Parties (TMF632)",
    )
    tmfc002_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmfc002_quote_party_role_rel",
        "quote_id", "role_id", string="Party Roles (TMF669)",
    )
    tmfc002_product_offering_ids = fields.Many2many(
        "product.template", "tmfc002_quote_offering_rel",
        "quote_id", "offering_id", string="Product Offerings (TMF620)",
    )
    tmfc002_billing_account_id = fields.Many2one(
        "tmf.billing.account", string="Billing Account (TMF666)",
        index=True, ondelete="set null",
    )
    tmfc002_agreement_ids = fields.Many2many(
        "tmf.agreement", "tmfc002_quote_agreement_rel",
        "quote_id", "agreement_id", string="Agreements (TMF651)",
    )
    tmfc002_poq_ids = fields.Many2many(
        "tmf.check.product.offering.qualification", "tmfc002_quote_poq_rel",
        "quote_id", "poq_id", string="Check POQ (TMF679)",
    )
    tmfc002_appointment_ids = fields.Many2many(
        "tmf.appointment", "tmfc002_quote_appointment_rel",
        "quote_id", "appointment_id", string="Appointments (TMF646)",
    )

    _TMFC002_QUOTE_KEYS = frozenset((
        "related_party_json", "billing_account_json", "agreement_json", "poq_json",
        "quote_item_ids",
    ))

    def _tmfc002_resolve_refs(self, changed_keys=None):
        ctx = {"skip_tmf_wiring": True}
        explicit = changed_keys or set()
        for rec in self:
            updates = {}

            def _rebuild(field_name, model, items, triggered):
                if not items and not triggered:
                    return
                ids = _resolve_ids(self.env, model, items)
                if set(ids) != set(rec[field_name].ids):
                    updates[field_name] = [(6, 0, ids)]

            party = [i for i in _as_list(rec.related_party_json) if isinstance(i, dict)]
            _rebuild("tmfc002_related_partner_ids", "res.partner",
                     [i for i in party if i.get("@type") not in PARTY_ROLE_TYPES],
                     "related_party_json" in explicit)
            _rebuild("tmfc002_party_role_ids", "tmf.party.role",
                     [i for i in party if i.get("@type") in PARTY_ROLE_TYPES],
                     "related_party_json" in explicit)
            _rebuild("tmfc002_agreement_ids", "tmf.agreement",
                     _as_list(rec.agreement_json), "agreement_json" in explicit)
            _rebuild("tmfc002_poq_ids", "tmf.check.product.offering.qualification",
                     _as_list(rec.poq_json), "poq_json" in explicit)

            # billingAccount (single ref, TMF648 carries a list)
            ba = _as_list(rec.billing_account_json)
            ba_id = str((ba[0] or {}).get("id") or "").strip() if ba else ""
            if ba_id:
                match = self.env["tmf.billing.account"].sudo().search(
                    [("tmf_id", "=", ba_id)], limit=1)
                if match and rec.tmfc002_billing_account_id.id != match.id:
                    updates["tmfc002_billing_account_id"] = match.id
            elif "billing_account_json" in explicit and rec.tmfc002_billing_account_id:
                updates["tmfc002_billing_account_id"] = False

            # Item-level refs: productOffering (TMF620) and appointment (TMF646)
            offering_refs, appointment_refs = [], []
            for item in rec.quote_item_ids:
                po = _loads(item.product_offering_json)
                if isinstance(po, dict) and po.get("id"):
                    offering_refs.append(po)
                appointment_refs.extend(_as_list(item.appointment_json))
            _rebuild("tmfc002_product_offering_ids", "product.template",
                     offering_refs, True)
            _rebuild("tmfc002_appointment_ids", "tmf.appointment",
                     appointment_refs, True)

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._tmfc002_resolve_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            changed = self._TMFC002_QUOTE_KEYS & set(vals.keys())
            if changed:
                self._tmfc002_resolve_refs(changed_keys=changed)
        return res
