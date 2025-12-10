from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        # 1. Run standard Odoo confirmation (creates delivery orders, etc.)
        res = super(SaleOrder, self).action_confirm()
        
        # 2. Custom TMF Logic: Create Services for each line
        for line in self.order_line:
            # Check if this product has a linked Specification
            # (We only create Services for things that have a Spec)
            spec = line.product_template_id.product_specification_id
            
            if spec:
                # If quantity is 2, we usually create 2 distinct service instances
                qty = int(line.product_uom_qty)
                for i in range(qty):
                    self.env['tmf.service'].create({
                        'name': f"{spec.name} - {self.partner_id.name}",
                        'partner_id': self.partner_id.id,
                        'product_specification_id': spec.id,
                        'order_line_id': line.id,
                        'state': 'active', # Auto-activate for this demo
                        'start_date': fields.Datetime.now()
                    })
        
        return res