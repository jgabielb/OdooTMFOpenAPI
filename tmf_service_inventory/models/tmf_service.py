# tmf_service.py
from odoo import api, fields, models
from odoo.http import request


class TMFService(models.Model):
    _name = 'tmf.service'
    _description = 'TMF638 Service (Service Inventory)'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Service Name", required=True)
    description = fields.Char(string="Description")  # ✅ add this to avoid AttributeError

    # Who owns this service?
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)

    # Service specification
    product_specification_id = fields.Many2one(
        'tmf.product.specification',
        string="Specification"
    )

    # Where did it come from?
    order_line_id = fields.Many2one(
        'sale.order.line',
        string="Origin Order Line"
    )

    # TMF fields
    service_type = fields.Char(string="Service Type")  # optional
    category = fields.Selection(
        [('CFS', 'CustomerFacingService'), ('RFS', 'ResourceFacingService')],
        default='CFS',
        string="Category (CFS/RFS)"
    )

    state = fields.Selection([
        ('feasabilityChecked', 'Feasability Checked'),
        ('designed', 'Designed'),
        ('reserved', 'Reserved'),
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ], default='inactive', string="State")

    operating_status = fields.Selection([
        ('pending', 'Pending'),
        ('configured', 'Configured'),
        ('starting', 'Starting'),
        ('running', 'Running'),
        ('degraded', 'Degraded'),
        ('failed', 'Failed'),
        ('limited', 'Limited'),
        ('stopping', 'Stopping'),
        ('stopped', 'Stopped'),
        ('unknown', 'Unknown'),
    ], default='unknown', string="Operating Status")

    is_service_enabled = fields.Boolean(default=True, string="Is Service Enabled")
    has_started = fields.Boolean(default=False, string="Has Started")
    start_mode = fields.Selection([
        ('0', 'Unknown'),
        ('1', 'Automatically by the managed environment'),
        ('2', 'Automatically by the owning device'),
        ('3', 'Manually by the Provider'),
        ('4', 'Manually by the Customer'),
        ('5', 'Any of the above'),
    ], default='1', string="Start Mode")
    is_stateful = fields.Boolean(default=True, string="Is Stateful")

    service_date = fields.Datetime(string="Service Date", default=fields.Datetime.now)
    start_date = fields.Datetime(string="Start Date", default=fields.Datetime.now)
    end_date = fields.Datetime(string="End Date")

    resource_id = fields.Many2one(
        'stock.lot',
        string="Supporting Resource",
        help="The physical/virtual resource supporting this service"
    )

    def _get_tmf_api_path(self):
        return "/serviceInventoryManagement/v5/service"

    def _abs_href(self, path: str) -> str:
        try:
            base = request.httprequest.host_url.rstrip("/")
            return f"{base}{path}"
        except Exception:
            return path

    def to_tmf_json(self):
        self.ensure_one()

        sid = self.tmf_id or str(self.id)
        href_path = f"/tmf-api{self._get_tmf_api_path()}/{sid}"
        href = self._abs_href(href_path)

        data = {
            "id": sid,
            "href": href,
            "@type": "Service",

            "name": self.name or "",
            "description": (self.description or self.name or ""),

            "state": self.state or "inactive",
            "operatingStatus": self.operating_status or "unknown",

            "category": self.category or "CFS",
            "serviceType": self.service_type or None,

            "isServiceEnabled": bool(self.is_service_enabled),
            "hasStarted": bool(self.has_started),
            "startMode": self.start_mode or "1",
            "isStateful": bool(self.is_stateful),

            "serviceDate": self.service_date.isoformat() if self.service_date else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
        }

        if self.partner_id:
            party_id = self.partner_id.tmf_id or str(self.partner_id.id)
            party_href = f"/tmf-api/partyManagement/v5/party/{party_id}"
            party_ref = {
                "id": party_id,
                "href": self._abs_href(party_href),
                "name": self.partner_id.name or "",
                "@type": "PartyRef",
                "@referredType": "Organization" if self.partner_id.is_company else "Individual",
            }
            data["relatedParty"] = [{
                "role": "customer",
                "partyOrPartyRole": party_ref,
                "@type": "RelatedPartyRefOrPartyRoleRef",
            }]

        if self.product_specification_id:
            spec_id = self.product_specification_id.tmf_id or str(self.product_specification_id.id)
            spec_href = f"/tmf-api/serviceCatalogManagement/v5/serviceSpecification/{spec_id}"
            data["serviceSpecification"] = {
                "id": spec_id,
                "href": self._abs_href(spec_href),
                "name": self.product_specification_id.name or "",
                "version": getattr(self.product_specification_id, "version", None) or None,
                "@type": "ServiceSpecificationRef",
                "@referredType": "ServiceSpecification",
            }

        if self.resource_id:
            rid = getattr(self.resource_id, "tmf_id", None) or str(self.resource_id.id)
            r_href = f"/tmf-api/resourceInventoryManagement/v5/resource/{rid}"
            data["supportingResource"] = [{
                "id": rid,
                "href": self._abs_href(r_href),
                "name": self.resource_id.name or self.resource_id.display_name or "",
                "@type": "ResourceRef",
                "@referredType": "Resource",
            }]

        return {k: v for k, v in data.items() if v is not None}

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='service',
                event_type='create',
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
                    api_name='service',
                    event_type='update',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [s.to_tmf_json() for s in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='service',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
