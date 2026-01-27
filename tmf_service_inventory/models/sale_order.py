# sale_order.py
from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()

        for line in self.order_line:
            spec = line.product_template_id.product_specification_id
            if not spec:
                continue

            qty = int(line.product_uom_qty)
            for i in range(qty):
                self.env['tmf.service'].create({
                    'name': f"{spec.name} - {self.partner_id.name}",
                    'partner_id': self.partner_id.id,
                    'product_specification_id': spec.id,
                    'order_line_id': line.id,

                    'category': 'CFS',
                    'state': 'active',
                    'operating_status': 'running',

                    'is_service_enabled': True,
                    'has_started': True,
                    'start_mode': '1',
                    'is_stateful': True,

                    'service_date': fields.Datetime.now(),
                    'start_date': fields.Datetime.now(),
                })

        return res
