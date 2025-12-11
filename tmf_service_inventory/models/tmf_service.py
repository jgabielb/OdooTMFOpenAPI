from odoo import api, fields, models


class TMFService(models.Model):
    _name = 'tmf.service'
    _description = 'TMF Customer Service (Installed Base)'
    _inherit = ['tmf.model.mixin']

    name = fields.Char(string="Service Name", required=True)

    # Who owns this service?
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)

    # What kind of service is it?
    product_specification_id = fields.Many2one(
        'product.specification',
        string="Specification"
    )

    # Where did it come from?
    order_line_id = fields.Many2one(
        'sale.order.line',
        string="Origin Order Line"
    )

    start_date = fields.Datetime(
        string="Start Date",
        default=fields.Datetime.now
    )

    # TMF Lifecycle
    state = fields.Selection([
        ('feasibilityChecked', 'Feasibility Checked'),
        ('designed', 'Designed'),
        ('reserved', 'Reserved'),
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('terminated', 'Terminated')
    ], default='inactive', string="Status")

    # Link Service -> Resource (One Service uses One Main Resource for now)
    resource_id = fields.Many2one(
        'stock.lot',   # or 'stock.production.lot' in your DB
        string="Supporting Resource",
        help="The physical device (SN) supporting this service"
    )

    # ---------- TMF639 base path ----------

    def _get_tmf_api_path(self):
        return "/serviceInventory/v4/service"

    # ---------- TMF639 JSON representation ----------

    def to_tmf_json(self):
        """Return TMF639 Service representation."""
        self.ensure_one()

        href = getattr(self, 'tmf_href', None)
        if not href:
            href = f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}"

        data = {
            "id": self.tmf_id or str(self.id),
            "href": href,
            "name": self.name,
            "description": self.name,
            "@type": "Service",
            "state": self.state or "inactive",
            "startDate": self.start_date.isoformat() if self.start_date else None,
        }

        # relatedParty (Customer)
        if self.partner_id:
            data["relatedParty"] = [{
                "id": self.partner_id.tmf_id or str(self.partner_id.id),
                "name": self.partner_id.name,
                "role": "Customer",
                "@referredType": "Individual" if not self.partner_id.is_company else "Organization",
            }]

        # serviceSpecification
        if self.product_specification_id:
            data["serviceSpecification"] = {
                "id": self.product_specification_id.tmf_id
                       or str(self.product_specification_id.id),
                "name": self.product_specification_id.name,
                "@referredType": "ServiceSpecification",
            }

        # supportingResource from resource_id
        if self.resource_id:
            data["supportingResource"] = [{
                "id": self.resource_id.tmf_id or str(self.resource_id.id),
                "name": self.resource_id.name or self.resource_id.display_name,
                "@referredType": "Resource",
            }]

        return data

    # ---------- Event hooks for /hub (TMF639 Service Inventory) ----------

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='service',          # <-- matches what you'll use in /hub
                event_type='create',         # <-- matches selection on tmf.hub.subscription
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
