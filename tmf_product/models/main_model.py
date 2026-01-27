from odoo import models, fields, api


# ------------------------------------------------------------
# Reverse link on Odoo product variant (REQUIRED for 2-way link)
# ------------------------------------------------------------
class ProductProduct(models.Model):
    _inherit = "product.product"

    tmf_product_id = fields.Many2one(
        "tmf.product",
        string="TMF Product",
        ondelete="set null",
        index=True,
    )


class TMFProduct(models.Model):
    _name = 'tmf.product'
    _description = 'Product'
    _inherit = ['tmf.model.mixin']

    # --- Core TMF fields ---
    description = fields.Char(string="description")
    is_bundle = fields.Boolean(string="isBundle")
    is_customer_visible = fields.Boolean(string="isCustomerVisible")
    name = fields.Char(string="name")
    order_date = fields.Datetime(string="orderDate")
    product_serial_number = fields.Char(string="productSerialNumber")
    start_date = fields.Datetime(string="startDate")
    termination_date = fields.Datetime(string="terminationDate")
    status = fields.Char(string="status")

    random_att = fields.Char(string="randomAtt")

    # --- Structured TMF attributes (JSON) ---
    agreement = fields.Json(string="agreement")
    billing_account = fields.Json(string="billingAccount")
    place = fields.Json(string="place")
    product = fields.Json(string="product")
    product_characteristic = fields.Json(string="productCharacteristic")
    product_offering = fields.Json(string="productOffering")
    product_order_item = fields.Json(string="productOrderItem")
    product_price = fields.Json(string="productPrice")
    product_relationship = fields.Json(string="productRelationship")
    product_specification = fields.Json(string="productSpecification")
    product_term = fields.Json(string="productTerm")
    realizing_resource = fields.Json(string="realizingResource")
    realizing_service = fields.Json(string="realizingService")
    related_party = fields.Json(string="relatedParty")

    # --- Bridge to Odoo product variant ---
    odoo_product_id = fields.Many2one(
        'product.product',
        string="Odoo Product",
        ondelete='set null',
        index=True
    )
    odoo_product_tmpl_id = fields.Many2one(
        'product.template',
        related='odoo_product_id.product_tmpl_id',
        store=True,
        readonly=True,
    )

    # -------------------------
    # Core bridge helper (SINGLE SOURCE OF TRUTH)
    # -------------------------
    def _make_odoo_product_saleable_and_linked(self, odoo_product):
        """
        Enforce the Odoo product is saleable and linked both ways.
        Uses `type` (your build does NOT have detailed_type).
        """
        if not odoo_product:
            return

        tmpl = odoo_product.product_tmpl_id.sudo()

        vals = {}
        if hasattr(tmpl, "sale_ok") and not tmpl.sale_ok:
            vals["sale_ok"] = True

        if hasattr(tmpl, "type") and tmpl.type not in ("service", "consu"):
            vals["type"] = "service"

        # Optional: keep names aligned for reporting/user friendliness
        if self.name and tmpl.name != self.name:
            vals["name"] = self.name

        if vals:
            tmpl.write(vals)

        # reverse link always
        odoo_product.sudo().write({"tmf_product_id": self.id})

    def _ensure_odoo_product_link(self):
        """
        Create/link a saleable Odoo product.variant for this TMF product.

        IMPORTANT: avoid recursion when called from write().
        """
        if self.env.context.get("tmf_skip_link"):
            return

        ProductTemplate = self.env['product.template'].sudo()

        for rec in self:
            if rec.odoo_product_id:
                rec._make_odoo_product_saleable_and_linked(rec.odoo_product_id)
                continue

            tmpl = ProductTemplate.create({
                "name": rec.name or "TMF Product",
                "sale_ok": True,
                "type": "service",
            })
            variant = tmpl.product_variant_id

            # Use context flag to avoid re-entering write() logic
            rec.with_context(tmf_skip_link=True).sudo().write({"odoo_product_id": variant.id})
            rec._make_odoo_product_saleable_and_linked(variant)

    # -------------------------
    # GUI actions
    # -------------------------
    def action_create_or_sync_odoo_product(self):
        for rec in self:
            rec._ensure_odoo_product_link()

    @api.onchange("odoo_product_id")
    def _onchange_odoo_product_id_make_saleable(self):
        for rec in self:
            if rec.odoo_product_id:
                rec._make_odoo_product_saleable_and_linked(rec.odoo_product_id)

    # ---------- TMF plumbing ----------
    def _get_tmf_api_path(self):
        return "/productManagement/v5/Product"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Product",
            "description": self.description,
            "isBundle": bool(self.is_bundle),
            "isCustomerVisible": bool(self.is_customer_visible),
            "name": self.name,
            "orderDate": self.order_date.isoformat() if self.order_date else None,
            "productSerialNumber": self.product_serial_number,
            "randomAtt": self.random_att,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "terminationDate": self.termination_date.isoformat() if self.termination_date else None,
            "agreement": self.agreement or None,
            "billingAccount": self.billing_account or None,
            "place": self.place or None,
            "product": self.product or None,
            "productCharacteristic": self.product_characteristic or None,
            "productOffering": self.product_offering or None,
            "productOrderItem": self.product_order_item or None,
            "productPrice": self.product_price or None,
            "productRelationship": self.product_relationship or None,
            "productSpecification": self.product_specification or None,
            "productTerm": self.product_term or None,
            "realizingResource": self.realizing_resource or None,
            "realizingService": self.realizing_service or None,
            "relatedParty": self.related_party or None,
            "status": self.status,
        }

    # ---------- Keep tmf.hub logic unchanged ----------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)

        # Auto link/create Odoo product for unified reporting
        for rec in recs:
            rec._ensure_odoo_product_link()
            rec._notify('product', 'create', rec)

        return recs

    def write(self, vals):
        res = super().write(vals)

        # Ensure consistency after edits:
        # - if user changed name and we already have an Odoo product, sync name + saleability
        # - if user linked an Odoo product, enforce link + sale_ok + type
        if not self.env.context.get("tmf_skip_link"):
            for rec in self:
                if 'odoo_product_id' in vals or 'name' in vals:
                    rec._ensure_odoo_product_link()

                rec._notify('product', 'update', rec)

        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='product',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass


# ------------------------------------------------------------
# TMF760 auxiliary persistence models
# Add resource_json so controllers can store/return exact schema objects
# ------------------------------------------------------------
class TmfCheckProductConfiguration(models.Model):
    _name = "tmf.check.product.configuration"
    _description = "TMF760 CheckProductConfiguration"

    tmf_id = fields.Char(index=True, required=True)
    href = fields.Char()
    state = fields.Char(default="acknowledged")
    request_payload = fields.Json()
    response_payload = fields.Json()

    # For 100% schema compliance: store the full resource returned
    resource_json = fields.Json()


class TmfQueryProductConfiguration(models.Model):
    _name = "tmf.query.product.configuration"
    _description = "TMF760 QueryProductConfiguration"

    tmf_id = fields.Char(index=True, required=True)
    href = fields.Char()
    state = fields.Char(default="acknowledged")
    request_payload = fields.Json()
    response_payload = fields.Json()

    # For 100% schema compliance: store the full resource returned
    resource_json = fields.Json()
