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


class ProductInventoryTMFC005Wiring(models.Model):
    """TMFC005 dependent API wiring for Product Inventory (TMF637-style Product).

    This wiring does NOT change TMF API behaviour. It enriches tmf.product
    records (extended by tmf_product_inventory) with Odoo stock relations
    so the ProductInventory component can navigate:

    - TMF Product -> Odoo product.template/product.product
    - TMF Product -> stock.location/stock.lot/stock.quant
    """

    _inherit = "tmf.product"

    # Raw reference fragments (if controllers choose to populate them)
    stock_location_ref_json = fields.Json(default=list, string="Location refs JSON (TMF673/675)")
    lot_ref_json = fields.Json(default=list, string="Batch/Lot refs JSON")

    # Odoo side relations (ODA/TMFC005 view)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Odoo Product Template",
        index=True, ondelete="set null",
    )
    product_id = fields.Many2one(
        "product.product", string="Odoo Product",
        index=True, ondelete="set null",
    )
    stock_location_id = fields.Many2one(
        "stock.location", string="Stock Location",
        index=True, ondelete="set null",
    )
    stock_lot_id = fields.Many2one(
        "stock.lot", string="Lot/Serial",
        index=True, ondelete="set null",
    )
    stock_quant_id = fields.Many2one(
        "stock.quant", string="Stock Quant",
        index=True, ondelete="set null",
    )

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            # 1) Map TMF product to Odoo product.template/product.product
            # Prefer existing explicit mapping if tmf_product already set it.
            if not rec.product_tmpl_id:
                # Heuristic: try to find product.template by name or tmf_id
                name = (rec.name or "").strip()
                tmpl = None
                if getattr(rec, "product_template_tmf_id", None):
                    tmpl = self.env["product.template"].sudo().search(
                        [("tmf_id", "=", rec.product_template_tmf_id)], limit=1
                    )
                if not tmpl and name:
                    tmpl = self.env["product.template"].sudo().search(
                        [("name", "=", name)], limit=1
                    )
                if tmpl:
                    updates["product_tmpl_id"] = tmpl.id

            if not rec.product_id and rec.product_tmpl_id:
                prod = self.env["product.product"].sudo().search(
                    [("product_tmpl_id", "=", rec.product_tmpl_id.id)], limit=1
                )
                if prod:
                    updates["product_id"] = prod.id

            # 2) Resolve locations and lots when hints are available
            payload = _loads(getattr(rec, "payload", None)) or {}

            loc_items = rec.stock_location_ref_json or payload.get("place") or []
            if isinstance(loc_items, dict):
                loc_items = [loc_items]
            if not rec.stock_location_id and loc_items:
                ids = _resolve_ids(self.env, "stock.location", loc_items, id_field="tmf_id")
                if not ids:
                    # Fallback by name
                    names = {str(i.get("name") or "").strip() for i in loc_items if isinstance(i, dict)}
                    if names:
                        match = self.env["stock.location"].sudo().search(
                            [("name", "in", list(names))], limit=1
                        )
                        if match:
                            ids = [match.id]
                if ids:
                    updates["stock_location_id"] = ids[0]

            lot_items = rec.lot_ref_json or payload.get("productInstance") or []
            if isinstance(lot_items, dict):
                lot_items = [lot_items]
            if not rec.stock_lot_id and lot_items:
                ids = _resolve_ids(self.env, "stock.lot", lot_items, id_field="tmf_id")
                if not ids:
                    # Fallback by serialNumber
                    serials = {str(i.get("serialNumber") or "").strip() for i in lot_items if isinstance(i, dict)}
                    if serials:
                        match = self.env["stock.lot"].sudo().search(
                            [("name", "in", list(serials))], limit=1
                        )
                        if match:
                            ids = [match.id]
                if ids:
                    updates["stock_lot_id"] = ids[0]

            # 3) If we have product + location (and optionally lot), try to find a stock.quant
            if not rec.stock_quant_id and rec.product_id and rec.stock_location_id:
                domain = [
                    ("product_id", "=", rec.product_id.id),
                    ("location_id", "=", rec.stock_location_id.id),
                ]
                if rec.stock_lot_id:
                    domain.append(("lot_id", "=", rec.stock_lot_id.id))
                quant = self.env["stock.quant"].sudo().search(domain, limit=1)
                if quant:
                    updates["stock_quant_id"] = quant.id

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
            wiring_keys = {"stock_location_ref_json", "lot_ref_json", "payload"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res
