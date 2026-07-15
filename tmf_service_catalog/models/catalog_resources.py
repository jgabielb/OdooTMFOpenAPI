# -*- coding: utf-8 -*-
"""TMF633 resources beyond catalog/serviceSpecification:
serviceCategory, serviceCandidate, importJob, exportJob (TMFC006 exposed surface).
"""
from odoo import api, fields, models


class TMFServiceCategory(models.Model):
    _name = 'tmf.service.category'
    _description = 'TMF633 ServiceCategory'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char(default='1.0')
    lifecycle_status = fields.Char(string="lifecycleStatus", default="active")
    last_update = fields.Datetime(string="lastUpdate")
    is_root = fields.Boolean(string="isRoot", default=True)
    parent_id = fields.Many2one('tmf.service.category', string='Parent Category',
                                ondelete='set null')
    child_ids = fields.One2many('tmf.service.category', 'parent_id',
                                string='Child Categories')
    valid_for = fields.Json(string="validFor")

    def _get_tmf_api_path(self):
        return '/serviceCatalogManagement/v4/serviceCategory'

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            'id': self.tmf_id or str(self.id),
            'href': f'/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}',
            'name': self.name,
            'description': self.description or '',
            'version': self.version or '1.0',
            'lifecycleStatus': self.lifecycle_status or 'active',
            'lastUpdate': self.last_update.isoformat() if self.last_update else None,
            'isRoot': not self.parent_id,
            'validFor': self.valid_for or None,
            '@type': 'ServiceCategory',
        }
        if self.parent_id:
            payload['parentId'] = self.parent_id.tmf_id or str(self.parent_id.id)
        return {k: v for k, v in payload.items() if v is not None}

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ('name', 'name'), ('description', 'description'),
            ('version', 'version'), ('lifecycleStatus', 'lifecycle_status'),
            ('validFor', 'valid_for'),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        parent_ref = str(data.get('parentId') or '').strip()
        if parent_ref:
            parent = self.env['tmf.service.category'].sudo().search(
                [('tmf_id', '=', parent_ref)], limit=1)
            if parent:
                vals['parent_id'] = parent.id
        if not partial and not vals.get('name'):
            vals.setdefault('name', 'ServiceCategory')
        return vals

    def _notify(self, action, payload):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name='serviceCategory',
                event_type=action,
                resource_json=payload,
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault('last_update', now)
        recs = super().create(vals_list)
        for rec in recs:
            rec._notify('create', rec.to_tmf_json())
        return recs

    def write(self, vals):
        vals.setdefault('last_update', fields.Datetime.now())
        res = super().write(vals)
        for rec in self:
            rec._notify('update', rec.to_tmf_json())
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for payload in payloads:
            self._notify('delete', payload)
        return res


class TMFServiceCandidate(models.Model):
    _name = 'tmf.service.candidate'
    _description = 'TMF633 ServiceCandidate'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char(default='1.0')
    lifecycle_status = fields.Char(string="lifecycleStatus", default="active")
    last_update = fields.Datetime(string="lastUpdate")
    valid_for = fields.Json(string="validFor")
    category = fields.Json(string="category")
    service_specification_id = fields.Many2one(
        'tmf.service.specification', string='Service Specification',
        ondelete='set null', index=True)
    service_specification_json = fields.Json(string="serviceSpecification")

    def _get_tmf_api_path(self):
        return '/serviceCatalogManagement/v4/serviceCandidate'

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            'id': self.tmf_id or str(self.id),
            'href': f'/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}',
            'name': self.name,
            'description': self.description or '',
            'version': self.version or '1.0',
            'lifecycleStatus': self.lifecycle_status or 'active',
            'lastUpdate': self.last_update.isoformat() if self.last_update else None,
            'validFor': self.valid_for or None,
            'category': self.category or None,
            '@type': 'ServiceCandidate',
        }
        if self.service_specification_id:
            spec = self.service_specification_id
            payload['serviceSpecification'] = {
                'id': spec.tmf_id or str(spec.id),
                'href': spec._tmf_href(),
                'name': spec.name,
                '@type': 'ServiceSpecificationRef',
            }
        elif self.service_specification_json:
            payload['serviceSpecification'] = self.service_specification_json
        return {k: v for k, v in payload.items() if v is not None}

    def _resolve_service_specification(self):
        """Resolve serviceSpecification JSON ref to the local record by tmf_id."""
        for rec in self:
            if rec.service_specification_id or not rec.service_specification_json:
                continue
            ref = rec.service_specification_json
            if isinstance(ref, list):
                ref = ref[0] if ref else {}
            ref_id = str((ref or {}).get('id') or '').strip()
            if not ref_id:
                continue
            spec = self.env['tmf.service.specification'].sudo().search(
                [('tmf_id', '=', ref_id)], limit=1)
            if spec:
                rec.with_context(skip_tmf_candidate_sync=True).write(
                    {'service_specification_id': spec.id})

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ('name', 'name'), ('description', 'description'),
            ('version', 'version'), ('lifecycleStatus', 'lifecycle_status'),
            ('validFor', 'valid_for'), ('category', 'category'),
            ('serviceSpecification', 'service_specification_json'),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if not partial and not vals.get('name'):
            vals.setdefault('name', 'ServiceCandidate')
        return vals

    def _notify(self, action, payload):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name='serviceCandidate',
                event_type=action,
                resource_json=payload,
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault('last_update', now)
        recs = super().create(vals_list)
        recs._resolve_service_specification()
        for rec in recs:
            rec._notify('create', rec.to_tmf_json())
        return recs

    def write(self, vals):
        vals.setdefault('last_update', fields.Datetime.now())
        res = super().write(vals)
        if 'service_specification_json' in vals and not self.env.context.get(
                'skip_tmf_candidate_sync'):
            self._resolve_service_specification()
        if not self.env.context.get('skip_tmf_candidate_sync'):
            for rec in self:
                rec._notify('update', rec.to_tmf_json())
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for payload in payloads:
            self._notify('delete', payload)
        return res


class TMFServiceCatalogExportJob(models.Model):
    _name = 'tmf.service.catalog.export.job'
    _description = 'TMF633 Service Catalog Export Job'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True, default='ExportJob')
    status = fields.Selection([
        ('inProgress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='completed', required=True)
    url = fields.Char(string='Export URL')

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [('name', 'name'), ('status', 'status'), ('url', 'url')]:
            if key in data:
                vals[field_name] = data.get(key)
        if not partial:
            vals.setdefault('name', 'ExportJob')
            vals.setdefault('status', 'completed')
        return vals

    def _get_tmf_api_path(self):
        return '/serviceCatalogManagement/v4/exportJob'

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

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceCatalogExportJob',
                    event_type='ExportJobCreateEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                pass
        return recs


class TMFServiceCatalogImportJob(models.Model):
    _name = 'tmf.service.catalog.import.job'
    _description = 'TMF633 Service Catalog Import Job'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True, default='ImportJob')
    status = fields.Selection([
        ('inProgress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='completed', required=True)
    url = fields.Char(string='Import URL')

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [('name', 'name'), ('status', 'status'), ('url', 'url')]:
            if key in data:
                vals[field_name] = data.get(key)
        if not partial:
            vals.setdefault('name', 'ImportJob')
            vals.setdefault('status', 'completed')
        return vals

    def _get_tmf_api_path(self):
        return '/serviceCatalogManagement/v4/importJob'

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

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceCatalogImportJob',
                    event_type='ImportJobCreateEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                pass
        return recs
