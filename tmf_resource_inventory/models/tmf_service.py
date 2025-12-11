from odoo import api, fields, models


class TMFService(models.Model):
    _inherit = 'tmf.service'

    # Link Service -> Resource (One Service uses One Main Resource for now)
    resource_id = fields.Many2one(
        'stock.lot',
        string="Supporting Resource",
        help="The physical device (SN) supporting this service"
    )

    # ---------- TMF639 metadata ----------

    def _get_tmf_api_path(self):
        # base path for Service Inventory
        return "/serviceInventory/v4/service"

    def to_tmf_json(self):
        """Return TMF639 Service representation."""
        self.ensure_one()

        href = getattr(self, 'tmf_href', None)
        if not href:
            href = f"/tmf-api{self._get_tmf_api_path()}/{self.tmf_id or self.id}"

        # very minimal mapping; extend as needed
        data = {
            "id": self.tmf_id or str(self.id),
            "href": href,
            "name": self.name,
            "description": self.description or self.name,
            "@type": "Service",
            "state": getattr(self, 'state', None) or "active",  # adjust to your field
        }

        # supportingResource (from TMF639)
        if self.resource_id:
            data["supportingResource"] = [{
                "id": self.resource_id.tmf_id or str(self.resource_id.id),
                "name": self.resource_id.name or self.resource_id.display_name,
                "@referredType": "Resource",
            }]

        return data

    # ---------- Event hooks for /hub (TMF639) ----------

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec.env['tmf.hub.subscription']._notify_subscribers(
                api_name='service',
                event_type='ServiceCreateEvent',
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
                    event_type='ServiceAttributeValueChangeEvent',
                    resource_json=rec.to_tmf_json(),
                )
            except Exception:
                continue
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='service',
                    event_type='ServiceDeleteEvent',
                    resource_json=resource,
                )
            except Exception:
                continue
        return res
