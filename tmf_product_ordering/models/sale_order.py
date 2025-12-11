from odoo import models, fields, api
import json

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'tmf.model.mixin']

    # TMF622 State Mapping
    # Odoo: draft -> TMF: Acknowledged
    # Odoo: sale -> TMF: InProgress
    # Odoo: done -> TMF: Completed
    # Odoo: cancel -> TMF: Cancelled
    
    tmf_status = fields.Selection([
        ('Acknowledged', 'Acknowledged'),
        ('InProgress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Rejected', 'Rejected')
    ], string="TMF Status", compute="_compute_tmf_status", store=True)

    description = fields.Text(string="Order Description")

    @api.depends('state')
    def _compute_tmf_status(self):
        for order in self:
            if order.state in ['draft', 'sent']:
                order.tmf_status = 'Acknowledged'
            elif order.state == 'sale':
                order.tmf_status = 'InProgress'
            elif order.state == 'done':
                order.tmf_status = 'Completed'
            elif order.state == 'cancel':
                order.tmf_status = 'Cancelled'
            else:
                order.tmf_status = 'Acknowledged'

    def write(self, vals):
        res = super().write(vals)
        if 'tmf_status' in vals:
            self._notify_tmf_subscribers()
        return res

    def _notify_tmf_subscribers(self):
        subs = self.env['tmf.hub.subscription'].sudo().search([
            ('api_name', '=', 'productOrder')
        ])
        body = json.dumps({
            "eventId": str(self.id),
            "eventTime": fields.Datetime.now(),
            "eventType": "ProductOrderStateChangeEvent",
            "event": self.to_tmf_json(),
            "@type": "ProductOrderStateChangeEvent"
        })
        # send HTTP POST to each sub.callback (using requests / external lib / queue)
    
    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.tmf_href,
            "description": self.description or self.name,
            "state": self.tmf_status,
            "orderDate": self.date_order.isoformat() if self.date_order else None,
            "@type": "ProductOrder",
            # Simplified orderItems example:
            "orderItem": [
                {
                    "id": line.tmf_id,
                    "action": line.tmf_action or "add",
                    "product": {
                        "id": line.product_id.id,
                        "name": line.product_id.name
                    },
                    "@type": "ProductOrderItem"
                }
                for line in self.order_line
            ],
            # Add other fields from TMF622 as needed
        }
    
    def _get_tmf_api_path(self):
        return "/productOrderingManagement/v4/productOrder"
    
    @property
    def tmf_href(self):
        base = "/tmf-api" + self._get_tmf_api_path()
        return f"{base}/{self.tmf_id}"

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    # We inherit mixin here too because Lines have their own IDs in TMF
    _inherit = ['sale.order.line', 'tmf.model.mixin']

    def _get_tmf_api_path(self):
        # Lines usually don't have a direct top-level API, but they need UUIDs
        return ""