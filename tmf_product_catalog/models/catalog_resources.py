from odoo import api, fields, models


class TMFProductCatalog(models.Model):
    _name = 'tmf.product.catalog'
    _description = 'TMF Product Catalog'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Text()
    version = fields.Char(default='1.0')
    lifecycle_status = fields.Selection([
        ('design', 'In Design'),
        ('active', 'Active'),
        ('retired', 'Retired'),
    ], default='active', string='Status')

    category_ids = fields.Many2many(
        'tmf.product.category',
        'tmf_product_catalog_category_rel',
        'catalog_id',
        'category_id',
        string='Categories',
    )

    def _get_tmf_api_path(self):
        return '/productCatalogManagement/v5/catalog'

    def to_tmf_json(self):
        self.ensure_one()
        return {
            'id': self.tmf_id or str(self.id),
            'href': f'/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}',
            'name': self.name,
            'description': self.description or '',
            'version': self.version or '1.0',
            'lifecycleStatus': {
                'design': 'In Design',
                'active': 'Active',
                'retired': 'Retired',
            }.get(self.lifecycle_status, 'Active'),
            '@type': 'Catalog',
            'category': [
                {
                    'id': c.tmf_id or str(c.id),
                    'href': f'/tmf-api/productCatalogManagement/v5/category/{c.tmf_id or c.id}',
                    'name': c.name,
                    '@type': 'CategoryRef',
                }
                for c in self.category_ids
            ],
        }

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='catalog',
                event_type='CatalogCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='catalog',
                    event_type='CatalogAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='catalog',
                    event_type='CatalogDeleteEvent',
                    resource_json=payload,
                )
            except Exception:
                continue
        return res


class TMFProductCategory(models.Model):
    _name = 'tmf.product.category'
    _description = 'TMF Product Category'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Text()
    version = fields.Char(default='1.0')
    lifecycle_status = fields.Selection([
        ('design', 'In Design'),
        ('active', 'Active'),
        ('retired', 'Retired'),
    ], default='active', string='Status')

    parent_id = fields.Many2one('tmf.product.category', string='Parent Category', ondelete='set null')
    child_ids = fields.One2many('tmf.product.category', 'parent_id', string='Child Categories')
    catalog_ids = fields.Many2many(
        'tmf.product.catalog',
        'tmf_product_catalog_category_rel',
        'category_id',
        'catalog_id',
        string='Catalogs',
    )

    def _get_tmf_api_path(self):
        return '/productCatalogManagement/v5/category'

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            'id': self.tmf_id or str(self.id),
            'href': f'/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}',
            'name': self.name,
            'description': self.description or '',
            'version': self.version or '1.0',
            'lifecycleStatus': {
                'design': 'In Design',
                'active': 'Active',
                'retired': 'Retired',
            }.get(self.lifecycle_status, 'Active'),
            '@type': 'Category',
        }
        if self.parent_id:
            payload['parentId'] = self.parent_id.tmf_id or str(self.parent_id.id)
        return payload

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='category',
                event_type='CategoryCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='category',
                    event_type='CategoryAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='category',
                    event_type='CategoryDeleteEvent',
                    resource_json=payload,
                )
            except Exception:
                continue
        return res


class TMFProductCatalogExportJob(models.Model):
    _name = 'tmf.product.catalog.export.job'
    _description = 'TMF Product Catalog Export Job'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True, default='ExportJob')
    status = fields.Selection([
        ('inProgress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='completed', required=True)
    url = fields.Char(string='Export URL')

    def _get_tmf_api_path(self):
        return '/productCatalogManagement/v5/exportJob'

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            'id': self.tmf_id or str(self.id),
            'href': f'/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}',
            'status': self.status,
            '@type': 'ExportJob',
        }
        if self.url:
            payload['url'] = self.url
        return payload

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='exportJob',
                event_type='ExportJobCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='exportJob',
                event_type='ExportJobStateChangeEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec


class TMFProductCatalogImportJob(models.Model):
    _name = 'tmf.product.catalog.import.job'
    _description = 'TMF Product Catalog Import Job'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True, default='ImportJob')
    status = fields.Selection([
        ('inProgress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='completed', required=True)
    url = fields.Char(string='Import URL')

    def _get_tmf_api_path(self):
        return '/productCatalogManagement/v5/importJob'

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            'id': self.tmf_id or str(self.id),
            'href': f'/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}',
            'status': self.status,
            '@type': 'ImportJob',
        }
        if self.url:
            payload['url'] = self.url
        return payload

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='importJob',
                event_type='ImportJobCreateEvent',
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass
        return rec
