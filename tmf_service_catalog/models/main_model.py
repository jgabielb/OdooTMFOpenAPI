from odoo import models, fields, api

class TMFServiceCatalog(models.Model):
    _name = 'tmf.service.catalog'
    _description = 'TMF633 ServiceCatalog'
    _inherit = ['tmf.model.mixin']

    # TMF core fields
    name = fields.Char(string="name", required=True)
    description = fields.Char(string="description")
    version = fields.Char(string="version")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    last_update = fields.Datetime(string="lastUpdate")

    # TMF633 shapes (these are NOT strings in TMF — they are arrays/objects)
    # Minimal: store JSON until you model them properly with relational tables.
    category = fields.Json(string="category")          # array of ServiceCategoryRef
    related_party = fields.Json(string="relatedParty") # array of RelatedPartyRefOrPartyRoleRef
    valid_for = fields.Json(string="validFor")         # TimePeriod object
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", copy=False, index=True)

    def _resolve_product_template(self):
        self.ensure_one()
        ProductTmpl = self.env["product.template"].sudo()
        if self.product_tmpl_id:
            return self.product_tmpl_id
        if self.tmf_id and "tmf_id" in ProductTmpl._fields:
            tmpl = ProductTmpl.search([("tmf_id", "=", str(self.tmf_id))], limit=1)
            if tmpl:
                return tmpl
        if self.name:
            tmpl = ProductTmpl.search([("name", "=", self.name)], limit=1)
            if tmpl:
                return tmpl
            vals = {"name": self.name}
            if "detailed_type" in ProductTmpl._fields:
                vals["detailed_type"] = "service"
            elif "type" in ProductTmpl._fields:
                vals["type"] = "service"
            if "tmf_id" in ProductTmpl._fields and self.tmf_id:
                vals["tmf_id"] = str(self.tmf_id)
            return ProductTmpl.create(vals)
        return ProductTmpl

    def _sync_product_template_link(self):
        for rec in self:
            tmpl = rec._resolve_product_template()
            if tmpl and rec.product_tmpl_id != tmpl:
                rec.with_context(skip_tmf_catalog_sync=True).write({"product_tmpl_id": tmpl.id})

    def _get_tmf_api_path(self):
        # TMF633 v4 resource base
        return "/tmf-api/serviceCatalogManagement/v4"

    def _tmf_href(self):
        self.ensure_one()
        # if tmf_id exists use it, else fallback to Odoo id
        rid = self.tmf_id or str(self.id)
        return f"{self._get_tmf_api_path()}/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id or str(self.id),
            "href": self._tmf_href(),
            "@type": "ServiceCatalog",
            "name": self.name or "",
            "description": self.description,
            "version": self.version,
            "lifecycleStatus": self.lifecycle_status or "active",
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "category": self.category or [],
            "relatedParty": self.related_party or [],
            "validFor": self.valid_for or None,
        }

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("last_update", now)
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_catalog_sync"):
            recs._sync_product_template_link()
        for rec in recs:
            rec._notify('serviceCatalog', 'create', rec)
        return recs

    def write(self, vals):
        vals.setdefault("last_update", fields.Datetime.now())
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_catalog_sync"):
            self._sync_product_template_link()
        for rec in self:
            rec._notify('serviceCatalog', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceCatalog',
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

class TMFServiceSpecification(models.Model):
    _name = 'tmf.service.specification'
    _description = 'TMF633 ServiceSpecification'
    # TMFC006: extend ServiceSpecification with foundational wiring helpers
    # for TMF634/TMF632/TMF669/TMF662 without changing CTK-visible behaviour.
    _inherit = ['tmf.model.mixin', 'tmfc006.wiring.tools']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char()
    lifecycle_status = fields.Char(string="lifecycleStatus", default="active")
    last_update = fields.Datetime(string="lastUpdate")

    is_bundle = fields.Boolean(string="isBundle", default=False)

    # keep JSON blobs for now (optional but TMF commonly carries them)
    related_party = fields.Json(string="relatedParty")
    valid_for = fields.Json(string="validFor")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", copy=False, index=True)

    def _resolve_product_template(self):
        self.ensure_one()
        ProductTmpl = self.env["product.template"].sudo()
        if self.product_tmpl_id:
            return self.product_tmpl_id
        if self.tmf_id and "tmf_id" in ProductTmpl._fields:
            tmpl = ProductTmpl.search([("tmf_id", "=", str(self.tmf_id))], limit=1)
            if tmpl:
                return tmpl
        if self.name:
            tmpl = ProductTmpl.search([("name", "=", self.name)], limit=1)
            if tmpl:
                return tmpl
            vals = {"name": self.name}
            if "detailed_type" in ProductTmpl._fields:
                vals["detailed_type"] = "service"
            elif "type" in ProductTmpl._fields:
                vals["type"] = "service"
            if "tmf_id" in ProductTmpl._fields and self.tmf_id:
                vals["tmf_id"] = str(self.tmf_id)
            return ProductTmpl.create(vals)
        return ProductTmpl

    def _sync_product_template_link(self):
        for rec in self:
            tmpl = rec._resolve_product_template()
            if tmpl and rec.product_tmpl_id != tmpl:
                rec.with_context(skip_tmf_catalog_sync=True).write({"product_tmpl_id": tmpl.id})

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"

    def _tmf_href(self):
        self.ensure_one()
        rid = self.tmf_id or str(self.id)
        return f"{self._get_tmf_api_path()}/{rid}"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id or str(self.id),
            "href": self._tmf_href(),
            "@type": "ServiceSpecification",
            "name": self.name or "",
            "description": self.description,
            "version": self.version,
            "lifecycleStatus": self.lifecycle_status or "active",
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "isBundle": bool(self.is_bundle),
            "relatedParty": self.related_party or [],
            "validFor": self.valid_for or None,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ls = vals.get("lifecycle_status")
            if ls in (False, None, ""):
                vals["lifecycle_status"] = "active"
            else:
                vals["lifecycle_status"] = str(ls).strip().lower()
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_catalog_sync"):
            recs._sync_product_template_link()
        return recs

    def write(self, vals):
        vals.setdefault("last_update", fields.Datetime.now())
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_catalog_sync"):
            self._sync_product_template_link()
        for rec in self:
            rec._notify('serviceSpecification', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceSpecification',
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
