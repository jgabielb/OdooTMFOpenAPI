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


class ProductOrderTMFC002Wiring(models.Model):
    """TMFC002 dependent API wiring for ProductOrder (TMF622)."""

    _inherit = "tmf.product.order"

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

    # Link to native Odoo sales order (commercial record)
    sale_order_id = fields.Many2one(
        "sale.order", string="Linked Odoo Sales Order",
        index=True, ondelete="set null",
    )

    def _resolve_tmf_refs(self):
        """Resolve TMF JSON reference IDs to local Odoo records.

        This does not change TMF622 API behaviour; it only enriches the
        ProductOrder view for ODA TMFC002 purposes.
        """

        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}
            payload = _loads(getattr(rec, "payload", None)) or {}

            # TMF632 relatedParty -> res.partner
            party_json = rec.related_party_json or payload.get("relatedParty") or []
            if not rec.related_partner_ids and party_json:
                ids = _resolve_ids(self.env, "res.partner", party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            # TMF620 productOffering -> product.template
            po_json = rec.product_offering_json or []
            if not po_json:
                # derive from order items: each item.productOffering
                for item in (payload.get("orderItem") or []):
                    if not isinstance(item, dict):
                        continue
                    po = item.get("productOffering") or {}
                    if isinstance(po, dict) and po.get("id"):
                        po_json.append(po)
            if not rec.product_offering_ids and po_json:
                ids = _resolve_ids(self.env, "product.template", po_json)
                if ids:
                    updates["product_offering_ids"] = [(6, 0, ids)]

            # TMF666 billingAccount -> tmf.billing.account
            if not rec.billing_account_id:
                ba = rec.billing_account_json or payload.get("billingAccount") or {}
                if isinstance(ba, dict):
                    ba_id = str(ba.get("id") or "").strip()
                    if ba_id:
                        match = self.env["tmf.billing.account"].sudo().search(
                            [("tmf_id", "=", ba_id)], limit=1
                        )
                        if match:
                            updates["billing_account_id"] = match.id

            # Optional: pre-order / qualification context linking
            # (These assume TMF controllers store refs in payload.)
            if not rec.poq_ids:
                poq = payload.get("productOfferingQualification") or []
                if isinstance(poq, dict):
                    poq = [poq]
                ids = _resolve_ids(self.env, "tmf.check.product.offering.qualification", poq)
                if ids:
                    updates["poq_ids"] = [(6, 0, ids)]

            if not rec.sq_ids:
                sq = payload.get("serviceQualification") or []
                if isinstance(sq, dict):
                    sq = [sq]
                ids = _resolve_ids(self.env, "tmf.service.qualification", sq)
                if ids:
                    updates["sq_ids"] = [(6, 0, ids)]

            if not rec.cart_ids:
                carts = payload.get("shoppingCart") or []
                if isinstance(carts, dict):
                    carts = [carts]
                ids = _resolve_ids(self.env, "tmf.shopping.cart", carts)
                if ids:
                    updates["cart_ids"] = [(6, 0, ids)]

            # Link to Odoo sale.order via client_order_ref = tmf_id (common pattern)
            if not rec.sale_order_id:
                so = self.env["sale.order"].sudo().search(
                    [("client_order_ref", "=", rec.tmf_id)], limit=1
                )
                if so:
                    updates["sale_order_id"] = so.id

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
                "related_party_json", "product_offering_json",
                "billing_account_json", "payload",
            }
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res
