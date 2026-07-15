# -*- coding: utf-8 -*-
"""TMF634 resources beyond resourceCatalog/resourceSpecification:
resourceCategory, resourceCandidate, importJob, exportJob (TMFC010 exposed surface).
"""
from odoo import api, fields, models


class TMFResourceCategory(models.Model):
    _name = 'tmf.resource.category'
    _description = 'TMF634 ResourceCategory'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char(default='1.0')
    lifecycle_status = fields.Char(string="lifecycleStatus", default="active")
    last_update = fields.Datetime(string="lastUpdate")
    parent_id = fields.Many2one('tmf.resource.category', string='Parent Category',
                                ondelete='set null')
    child_ids = fields.One2many('tmf.resource.category', 'parent_id',
                                string='Child Categories')
    valid_for = fields.Json(string="validFor")

    def _get_tmf_api_path(self):
        return '/resourceCatalogManagement/v5/resourceCategory'

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
            '@type': 'ResourceCategory',
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
            parent = self.env['tmf.resource.category'].sudo().search(
                [('tmf_id', '=', parent_ref)], limit=1)
            if parent:
                vals['parent_id'] = parent.id
        if not partial and not vals.get('name'):
            vals.setdefault('name', 'ResourceCategory')
        return vals

    def _notify(self, action, payload):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name='resourceCategory',
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


class TMFResourceCandidate(models.Model):
    _name = 'tmf.resource.candidate'
    _description = 'TMF634 ResourceCandidate'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True)
    description = fields.Char()
    version = fields.Char(default='1.0')
    lifecycle_status = fields.Char(string="lifecycleStatus", default="active")
    last_update = fields.Datetime(string="lastUpdate")
    valid_for = fields.Json(string="validFor")
    category = fields.Json(string="category")
    resource_specification_id = fields.Many2one(
        'tmf.resource.specification', string='Resource Specification',
        ondelete='set null', index=True)
    resource_specification_json = fields.Json(string="resourceSpecification")

    def _get_tmf_api_path(self):
        return '/resourceCatalogManagement/v5/resourceCandidate'

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
            '@type': 'ResourceCandidate',
        }
        if self.resource_specification_id:
            spec = self.resource_specification_id
            payload['resourceSpecification'] = {
                'id': spec.tmf_id or str(spec.id),
                'href': getattr(spec, 'href', None),
                'name': spec.name,
                '@type': 'ResourceSpecificationRef',
            }
        elif self.resource_specification_json:
            payload['resourceSpecification'] = self.resource_specification_json
        return {k: v for k, v in payload.items() if v is not None}

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [
            ('name', 'name'), ('description', 'description'),
            ('version', 'version'), ('lifecycleStatus', 'lifecycle_status'),
            ('validFor', 'valid_for'), ('category', 'category'),
            ('resourceSpecification', 'resource_specification_json'),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if not partial and not vals.get('name'):
            vals.setdefault('name', 'ResourceCandidate')
        return vals

    def _resolve_resource_specification(self):
        for rec in self:
            if rec.resource_specification_id or not rec.resource_specification_json:
                continue
            ref = rec.resource_specification_json
            if isinstance(ref, list):
                ref = ref[0] if ref else {}
            ref_id = str((ref or {}).get('id') or '').strip()
            if not ref_id:
                continue
            spec = self.env['tmf.resource.specification'].sudo().search(
                [('tmf_id', '=', ref_id)], limit=1)
            if spec:
                rec.with_context(skip_tmf_candidate_sync=True).write(
                    {'resource_specification_id': spec.id})

    def _notify(self, action, payload):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name='resourceCandidate',
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
        recs._resolve_resource_specification()
        for rec in recs:
            rec._notify('create', rec.to_tmf_json())
        return recs

    def write(self, vals):
        vals.setdefault('last_update', fields.Datetime.now())
        res = super().write(vals)
        if 'resource_specification_json' in vals and not self.env.context.get(
                'skip_tmf_candidate_sync'):
            self._resolve_resource_specification()
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


class TMFResourceCatalogExportJob(models.Model):
    _name = 'tmf.resource.catalog.export.job'
    _description = 'TMF634 Resource Catalog Export Job'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True, default='ExportJob')
    status = fields.Selection([
        ('inProgress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='completed', required=True)
    url = fields.Char(string='Export URL')

    def _get_tmf_api_path(self):
        return '/resourceCatalogManagement/v5/exportJob'

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

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [('name', 'name'), ('status', 'status'), ('url', 'url')]:
            if key in data:
                vals[field_name] = data.get(key)
        if not partial:
            vals.setdefault('name', 'ExportJob')
            vals.setdefault('status', 'completed')
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='resourceCatalogExportJob',
                    event_type='ExportJobCreateEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                pass
        return recs


class TMFResourceCatalogImportJob(models.Model):
    _name = 'tmf.resource.catalog.import.job'
    _description = 'TMF634 Resource Catalog Import Job'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(required=True, default='ImportJob')
    status = fields.Selection([
        ('inProgress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='completed', required=True)
    url = fields.Char(string='Import URL')

    def _get_tmf_api_path(self):
        return '/resourceCatalogManagement/v5/importJob'

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

    def from_tmf_json(self, data, partial=False):
        vals = {}
        for key, field_name in [('name', 'name'), ('status', 'status'), ('url', 'url')]:
            if key in data:
                vals[field_name] = data.get(key)
        if not partial:
            vals.setdefault('name', 'ImportJob')
            vals.setdefault('status', 'completed')
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='resourceCatalogImportJob',
                    event_type='ImportJobCreateEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                pass
        return recs
