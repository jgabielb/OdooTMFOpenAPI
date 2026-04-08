# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid
import json

API_BASE = "/tmf-api/productOfferingQualificationManagement/v5"


# ----------------------------
# Helpers
# ----------------------------
def _filter_top_level_fields(payload, fields_filter):
    """
    TMF spec:
    - ?fields applies ONLY to first-level attributes
    - Must always preserve: id, href, @type
    """
    if not fields_filter:
        return payload

    allowed = {f.strip() for f in str(fields_filter).split(",") if f.strip()}
    allowed.update({"id", "href", "@type"})
    return {k: v for k, v in payload.items() if k in allowed}


def _dt_to_iso_z(dtval):
    if not dtval:
        return None
    if isinstance(dtval, str):
        return dtval
    try:
        return dtval.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        return str(dtval)


def _as_obj(val, default=None):
    """Accept dict OR JSON-string; always return dict."""
    if default is None:
        default = {}
    if val is None:
        return default
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return default
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else default
        except Exception:
            return default
    return default


def _as_arr(val, default=None):
    """Accept list OR JSON-string; always return list."""
    if default is None:
        default = []
    if val is None:
        return default
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return default
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else default
        except Exception:
            return default
    return default


# -------------------------------------------------------------------------
# QueryProductOfferingQualification
# -------------------------------------------------------------------------
class TMFQueryProductOfferingQualification(models.Model):
    _name = "tmf.query.product.offering.qualification"
    _description = "TMF679 QueryProductOfferingQualification"
    _rec_name = "tmf_id"
    _inherit = ["tmf.model.mixin"]

    tmf_id = fields.Char(string="id", required=True, index=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(string="href", compute="_compute_href", store=False)

    tmf_type = fields.Char(string="@type", default="QueryProductOfferingQualification", required=True)
    description = fields.Text(string="description")

    effective_qualification_date = fields.Datetime(string="effectiveQualificationDate", default=fields.Datetime.now)
    creation_date = fields.Datetime(string="creationDate", default=fields.Datetime.now, readonly=True)

    # IMPORTANT: DB column is jsonb -> use fields.Json (NOT Text)
    # Must NEVER be NULL -> required=True + default dict with @type
    search_criteria_json = fields.Json(
        string="searchCriteria",
        required=True,
        default=lambda self: {"@type": "ProductOfferingQualificationSearchCriteria"},
    )

    # CTK wants array
    related_party_json = fields.Json(string="relatedParty", default=list)
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Draft Sale Order", ondelete="set null")

    def _resolve_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        if self.partner_id and self.partner_id.exists():
            return self.partner_id
        parties = _as_arr(self.related_party_json, default=[])
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            pname = party.get("name")
            if pid:
                partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
                if not partner and str(pid).isdigit():
                    partner = Partner.browse(int(pid))
                if partner and partner.exists():
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
        return Partner.browse([])

    def _resolve_product_template(self):
        self.ensure_one()
        ProductTmpl = self.env["product.template"].sudo()
        if self.product_tmpl_id and self.product_tmpl_id.exists():
            return self.product_tmpl_id

        criteria = _as_obj(self.search_criteria_json, default={})
        candidates = [
            criteria.get("id"),
            (criteria.get("productOffering") or {}).get("id") if isinstance(criteria.get("productOffering"), dict) else None,
            (criteria.get("product") or {}).get("id") if isinstance(criteria.get("product"), dict) else None,
        ]
        for cid in candidates:
            if not cid:
                continue
            tmpl = ProductTmpl.search([("tmf_id", "=", str(cid))], limit=1)
            if not tmpl and str(cid).isdigit():
                tmpl = ProductTmpl.browse(int(cid))
            if tmpl and tmpl.exists():
                return tmpl
        return ProductTmpl.browse([])

    def _sync_odoo_links(self):
        SaleOrder = self.env["sale.order"].sudo()
        for rec in self:
            partner = rec._resolve_partner()
            if partner and partner.exists() and rec.partner_id != partner:
                rec.partner_id = partner.id

            tmpl = rec._resolve_product_template()
            if tmpl and tmpl.exists() and rec.product_tmpl_id != tmpl:
                rec.product_tmpl_id = tmpl.id

            try:
                if rec.sale_order_id and rec.sale_order_id.exists():
                    continue
                if not rec.partner_id:
                    continue
                so = SaleOrder.search(
                    [("partner_id", "=", rec.partner_id.id), ("state", "=", "draft"), ("client_order_ref", "=", rec.tmf_id)],
                    limit=1,
                )
                if not so:
                    so = SaleOrder.create(
                        {
                            "partner_id": rec.partner_id.id,
                            "client_order_ref": rec.tmf_id,
                            "origin": f"TMF679-Query:{rec.tmf_id}",
                        }
                    )
                rec.sale_order_id = so.id
            except Exception:
                pass

    state = fields.Selection(
        [
            ("inProgress", "In Progress"),
            ("done", "Done"),
            ("terminatedWithError", "Terminated With Error"),
        ],
        string="state",
        required=True,
        default="done",
    )

    def _compute_href(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            rec.href = f"{base_url}{API_BASE}/queryProductOfferingQualification/{rec.tmf_id}"

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")

        sc = _as_obj(self.search_criteria_json, default={})
        sc.setdefault("@type", "ProductOfferingQualificationSearchCriteria")  # CTK required

        data = {
            "id": self.tmf_id,
            "href": f"{host_url}{API_BASE}/queryProductOfferingQualification/{self.tmf_id}",
            "@type": "QueryProductOfferingQualification",
            "creationDate": _dt_to_iso_z(self.creation_date),
            "effectiveQualificationDate": _dt_to_iso_z(self.effective_qualification_date),
            "state": self.state or "done",
            "searchCriteria": sc,  # object + @type
            "relatedParty": _as_arr(self.related_party_json, default=[]),
            "description": self.description or "",  # must be string
        }
        return _filter_top_level_fields(data, fields_filter)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ensure JSON fields are dict/list (not string)
            sc = vals.get("search_criteria_json")
            if isinstance(sc, str):
                sc = _as_obj(sc, default={})
            sc = sc or {}
            sc.setdefault("@type", "ProductOfferingQualificationSearchCriteria")
            vals["search_criteria_json"] = sc

            rp = vals.get("related_party_json")
            if isinstance(rp, str):
                rp = _as_arr(rp, default=[])
            vals["related_party_json"] = rp or []

            desc = vals.get("description")
            vals["description"] = desc if isinstance(desc, str) else (desc or "")

        recs = super().create(vals_list)
        recs._sync_odoo_links()
        return recs

    def write(self, vals):
        if "search_criteria_json" in vals:
            sc = vals.get("search_criteria_json")
            if isinstance(sc, str):
                sc = _as_obj(sc, default={})
            sc = sc or {}
            sc.setdefault("@type", "ProductOfferingQualificationSearchCriteria")
            vals["search_criteria_json"] = sc

        if "related_party_json" in vals:
            rp = vals.get("related_party_json")
            if isinstance(rp, str):
                rp = _as_arr(rp, default=[])
            vals["related_party_json"] = rp or []

        if "description" in vals:
            desc = vals.get("description")
            vals["description"] = desc if isinstance(desc, str) else (desc or "")

        res = super().write(vals)
        if any(k in vals for k in ("related_party_json", "search_criteria_json", "partner_id", "product_tmpl_id", "sale_order_id")):
            self._sync_odoo_links()
        return res

    @api.model
    def create_from_json(self, data):
        data = data or {}
        sc = data.get("searchCriteria") or {}
        if isinstance(sc, str):
            sc = _as_obj(sc, default={})
        sc.setdefault("@type", "ProductOfferingQualificationSearchCriteria")

        rp = data.get("relatedParty") or []
        if isinstance(rp, str):
            rp = _as_arr(rp, default=[])

        return self.create({
            "description": data.get("description") if isinstance(data.get("description"), str) else (data.get("description") or ""),
            "state": data.get("state") or "done",
            "related_party_json": rp,
            "search_criteria_json": sc,
        })


# -------------------------------------------------------------------------
# CheckProductOfferingQualification
# -------------------------------------------------------------------------
class TMFCheckProductOfferingQualification(models.Model):
    _name = "tmf.check.product.offering.qualification"
    _description = "TMF679 CheckProductOfferingQualification"
    _rec_name = "tmf_id"
    _inherit = ["tmf.model.mixin"]

    tmf_id = fields.Char(string="TMF ID", required=True, index=True, default=lambda self: str(uuid.uuid4()))
    href = fields.Char(string="Resource URL", compute="_compute_href", store=False)

    tmf_type = fields.Char(string="TMF Type", default="CheckProductOfferingQualification", required=True)
    description = fields.Text(string="Description")

    effective_qualification_date = fields.Datetime(
        string="Qualification Date",
        required=True,
        default=fields.Datetime.now,
    )

    qualification_result = fields.Selection(
        [
            ("qualified", "Qualified"),
            ("unableToProvide", "Unable To Provide"),
            ("insufficientInformation", "Insufficient Information"),
        ],
        string="Qualification Result",
        required=True,
        default="qualified",
    )

    state = fields.Selection(
        [
            ("inProgress", "In Progress"),
            ("done", "Done"),
            ("terminatedWithError", "Terminated With Error"),
        ],
        string="state",
        required=True,
        default="done",
    )

    item_ids = fields.One2many(
        "tmf.check.poq.item",
        "parent_id",
        string="Qualification Items",
    )

    related_party_json = fields.Json(string="Related Party Payload", default=list)
    partner_id = fields.Many2one("res.partner", string="Related Party", ondelete="set null")
    product_tmpl_id = fields.Many2one("product.template", string="Product", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Draft Sales Order", ondelete="set null")

    def _resolve_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        if self.partner_id and self.partner_id.exists():
            return self.partner_id
        parties = _as_arr(self.related_party_json, default=[])
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            pname = party.get("name")
            if pid:
                partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
                if not partner and str(pid).isdigit():
                    partner = Partner.browse(int(pid))
                if partner and partner.exists():
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
        return Partner.browse([])

    def _resolve_product_template(self):
        self.ensure_one()
        ProductTmpl = self.env["product.template"].sudo()
        if self.product_tmpl_id and self.product_tmpl_id.exists():
            return self.product_tmpl_id
        for item in self.item_ids:
            prod = _as_obj(item.product_json, default={})
            pid = prod.get("id")
            if not pid:
                continue
            tmpl = ProductTmpl.search([("tmf_id", "=", str(pid))], limit=1)
            if not tmpl and str(pid).isdigit():
                tmpl = ProductTmpl.browse(int(pid))
            if tmpl and tmpl.exists():
                return tmpl
        return ProductTmpl.browse([])

    def _sync_odoo_links(self):
        SaleOrder = self.env["sale.order"].sudo()
        for rec in self:
            partner = rec._resolve_partner()
            if partner and partner.exists() and rec.partner_id != partner:
                rec.partner_id = partner.id

            tmpl = rec._resolve_product_template()
            if tmpl and tmpl.exists() and rec.product_tmpl_id != tmpl:
                rec.product_tmpl_id = tmpl.id

            try:
                if rec.sale_order_id and rec.sale_order_id.exists():
                    continue
                if not rec.partner_id:
                    continue
                so = SaleOrder.search(
                    [("partner_id", "=", rec.partner_id.id), ("state", "=", "draft"), ("client_order_ref", "=", rec.tmf_id)],
                    limit=1,
                )
                if not so:
                    so = SaleOrder.create(
                        {
                            "partner_id": rec.partner_id.id,
                            "client_order_ref": rec.tmf_id,
                            "origin": f"TMF679-Check:{rec.tmf_id}",
                        }
                    )
                rec.sale_order_id = so.id
            except Exception:
                pass

    def _compute_href(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            rec.href = f"{base_url}{API_BASE}/checkProductOfferingQualification/{rec.tmf_id}"

    def to_tmf_json(self, host_url="", fields_filter=None):
        host_url = (host_url or "").rstrip("/")

        data = {
            "id": self.tmf_id,
            "href": f"{host_url}{API_BASE}/checkProductOfferingQualification/{self.tmf_id}",
            "@type": self.tmf_type or "CheckProductOfferingQualification",
            "description": self.description or "",
            "effectiveQualificationDate": _dt_to_iso_z(self.effective_qualification_date),
            "qualificationResult": self.qualification_result or "qualified",
            "state": self.state or "done",
            "creationDate": _dt_to_iso_z(self.create_date),
            "checkProductOfferingQualificationItem": [item.to_tmf_json() for item in self.item_ids],
            "relatedParty": _as_arr(self.related_party_json, default=[]),
        }

        data = {k: v for k, v in data.items() if v is not None}
        return _filter_top_level_fields(data, fields_filter)

    @api.model
    def create_from_json(self, data):
        data = data or {}

        rp = data.get("relatedParty") or []
        if isinstance(rp, str):
            rp = _as_arr(rp, default=[])

        vals = {
            "description": data.get("description") if isinstance(data.get("description"), str) else (data.get("description") or ""),
            "qualification_result": data.get("qualificationResult") or "qualified",
            "state": data.get("state") or "inProgress",
            "related_party_json": rp,
        }

        if data.get("effectiveQualificationDate"):
            vals["effective_qualification_date"] = str(data["effectiveQualificationDate"]).replace("Z", "")

        record = self.create(vals)

        items = data.get("checkProductOfferingQualificationItem") or []
        if items == []:
            items = [{"product": {"@type": "ProductRef"}, "qualificationItemResult": "qualified", "state": "done"}]

        for item_data in items:
            item_data = item_data or {}
            prod = item_data.get("product") or {}
            if isinstance(prod, str):
                prod = _as_obj(prod, default={})
            prod = prod or {}
            prod.setdefault("@type", "ProductRef")

            self.env["tmf.check.poq.item"].create({
                "parent_id": record.id,
                "tmf_id": item_data.get("id") or str(uuid.uuid4()),
                "qualification_item_result": item_data.get("qualificationItemResult", "qualified"),
                "product_json": prod,
                "state": item_data.get("state", "done"),
            })

        record._sync_odoo_links()
        return record

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "related_party_json" in vals and isinstance(vals["related_party_json"], str):
                vals["related_party_json"] = _as_arr(vals["related_party_json"], default=[])
            if "description" in vals:
                desc = vals.get("description")
                vals["description"] = desc if isinstance(desc, str) else (desc or "")

        recs = super().create(vals_list)
        recs._sync_odoo_links()
        for rec in recs:
            rec._notify("checkProductOfferingQualification", "create")
        return recs

    def write(self, vals):
        if "related_party_json" in vals and isinstance(vals["related_party_json"], str):
            vals["related_party_json"] = _as_arr(vals["related_party_json"], default=[])
        if "description" in vals:
            desc = vals.get("description")
            vals["description"] = desc if isinstance(desc, str) else (desc or "")

        old_states = {rec.id: rec.state for rec in self} if "state" in vals else {}
        res = super().write(vals)
        if any(k in vals for k in ("related_party_json", "partner_id", "product_tmpl_id", "sale_order_id")):
            self._sync_odoo_links()
        for rec in self:
            if "state" in vals and vals["state"] != old_states.get(rec.id):
                rec._notify("checkProductOfferingQualification", "stateChange")
            else:
                rec._notify("checkProductOfferingQualification", "attributeValueChange")
        return res

    def _notify(self, api_name, event_suffix):
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=api_name,
                event_type=event_suffix,
                resource_json=self.to_tmf_json(),
            )
        except Exception:
            pass


# -------------------------------------------------------------------------
# CheckProductOfferingQualificationItem
# -------------------------------------------------------------------------
class TMFCheckProductOfferingQualificationItem(models.Model):
    _name = "tmf.check.poq.item"
    _description = "CheckProductOfferingQualificationItem"

    parent_id = fields.Many2one(
        "tmf.check.product.offering.qualification",
        required=True,
        ondelete="cascade",
    )

    tmf_id = fields.Char(string="Item ID", required=True, default=lambda self: str(uuid.uuid4()))
    tmf_type = fields.Char(string="TMF Type", required=True, default="CheckProductOfferingQualificationItem")

    # JSONB object, MUST have @type for CTK. For TMF679 the discriminator
    # is resolved via oneOf(ProductRef, Product), so we default to
    # "ProductRef" (a pure reference) when we only know the identifier.
    product_json = fields.Json(
        string="Product Payload",
        required=True,
        default=lambda self: {"@type": "ProductRef"},
    )

    qualification_item_result = fields.Selection(
        [
            ("qualified", "Qualified"),
            ("unableToProvide", "Unable To Provide"),
        ],
        string="qualificationItemResult",
        required=True,
        default="qualified",
    )

    state = fields.Selection(
        [
            ("done", "Done"),
            ("terminatedWithError", "Terminated With Error"),
        ],
        string="state",
        required=True,
        default="done",
    )

    def to_tmf_json(self):
        self.ensure_one()
        prod = _as_obj(self.product_json, default={})

        # ------------------------------------------------------------------
        # CTK / TMF679 compliance:
        #   product is defined as ProductRefOrValue (oneOf ProductRef, Product)
        #   and the JSON Schema requires it to match EXACTLY one schema.
        #
        # Historical records may have stored:
        #   - product_json = {} or null
        #   - product_json missing an "id" field
        # which causes CTK to raise:
        #   /checkProductOfferingQualificationItem/0/product must match
        #   exactly one schema in oneOf
        # because the empty object matches none of the sub‑schemas.
        #
        # To guarantee an unambiguous schema match for ALL records (including
        # legacy ones), we normalize as follows:
        #   1) Always emit a dict.
        #   2) Always set an explicit @type discriminator, preferring
        #      "ProductRef" when we only have an identifier (reference) and
        #      falling back to "Product" when the payload clearly includes
        #      value/instance fields.
        #   3) Always ensure there is an "id"; if missing, infer it from
        #      the linked product template or, as a last resort, from the
        #      item id itself. This makes the payload a valid ProductRef.
        # ------------------------------------------------------------------

        if not isinstance(prod, dict):
            prod = {}

        # Try to infer a stable product id
        inferred_id = prod.get("id")
        if not inferred_id:
            # Prefer an explicit Odoo product template link when available
            parent = self.parent_id
            tmpl = getattr(parent, "product_tmpl_id", False)
            if tmpl and getattr(tmpl, "tmf_id", False):
                inferred_id = str(tmpl.tmf_id)
            elif tmpl and getattr(tmpl, "id", False):
                inferred_id = str(tmpl.id)
            else:
                # Last resort: a stable, but synthetic, identifier based on
                # the item id so that CTK sees a non‑empty ProductRef.
                inferred_id = str(self.tmf_id)

        prod["id"] = inferred_id

        # Decide on the most appropriate @type discriminator.
        # If the payload looks like a pure reference (only id/href/@referredType),
        # we explicitly mark it as ProductRef. Otherwise, we mark it as Product
        # to align with the ProductRefOrValue oneOf(ProductRef, Product)
        # discriminator expectations in the CTK JSON Schema.
        current_type = prod.get("@type")
        if not current_type:
            # Heuristic: treat minimal payloads as references
            ref_keys = {"id", "href", "@referredType"}
            non_ref_keys = {k for k in prod.keys() if k not in ref_keys}
            prod["@type"] = "ProductRef" if not non_ref_keys else "Product"
        else:
            # Normalize unexpected values into one of the two expected types
            if current_type not in ("ProductRef", "Product"):
                # unknown/legacy /ProductRefOrValue/ etc -> downgrade to ProductRef
                # for minimal payloads, or Product for richer ones
                ref_keys = {"id", "href", "@referredType"}
                non_ref_keys = {k for k in prod.keys() if k not in ref_keys}
                prod["@type"] = "ProductRef" if not non_ref_keys else "Product"

        # For a pure reference, explicitly declare the referred type to
        # avoid any ambiguity in validators that do not fully honor the
        # OpenAPI discriminator mapping. TMF examples consistently use
        # "@referredType": "Product" for ProductRef instances.
        if prod.get("@type") == "ProductRef":
            prod.setdefault("@referredType", "Product")

        return {
            "id": self.tmf_id,
            "@type": self.tmf_type,
            "product": prod,
            "qualificationItemResult": self.qualification_item_result,
            "state": self.state,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prod = vals.get("product_json")
            if isinstance(prod, str):
                prod = _as_obj(prod, default={})
            prod = prod or {}
            prod.setdefault("@type", "ProductRef")
            vals["product_json"] = prod
        return super().create(vals_list)

    def write(self, vals):
        if "product_json" in vals:
            prod = vals.get("product_json")
            if isinstance(prod, str):
                prod = _as_obj(prod, default={})
            prod = prod or {}
            prod.setdefault("@type", "ProductRef")
            vals["product_json"] = prod
        return super().write(vals)
