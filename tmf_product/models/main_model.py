from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.product'
    _description = 'Product'
    _inherit = ['tmf.model.mixin']

    description = fields.Char(string="description", help="Is the description of the product. It could be copied from the description of the Product Offering.")
    is_bundle = fields.Boolean(string="isBundle", help="If true, the product is a ProductBundle which is an instantiation of a BundledProductOffering. If fa")
    is_customer_visible = fields.Boolean(string="isCustomerVisible", help="If true, the product is visible by the customer.")
    name = fields.Char(string="name", help="Name of the product. It could be the same as the name of the product offering")
    order_date = fields.Datetime(string="orderDate", help="Is the date when the product was ordered")
    product_serial_number = fields.Char(string="productSerialNumber", help="Is the serial number for the product. This is typically applicable to tangible products e.g. Broadba")
    random_att = fields.Char(string="randomAtt", help="")
    start_date = fields.Datetime(string="startDate", help="Is the date from which the product starts")
    termination_date = fields.Datetime(string="terminationDate", help="Is the date when the product was terminated")
    agreement = fields.Char(string="agreement", help="")
    billing_account = fields.Char(string="billingAccount", help="")
    place = fields.Char(string="place", help="")
    product = fields.Char(string="product", help="")
    product_characteristic = fields.Char(string="productCharacteristic", help="")
    product_offering = fields.Char(string="productOffering", help="")
    product_order_item = fields.Char(string="productOrderItem", help="")
    product_price = fields.Char(string="productPrice", help="")
    product_relationship = fields.Char(string="productRelationship", help="")
    product_specification = fields.Char(string="productSpecification", help="")
    product_term = fields.Char(string="productTerm", help="")
    realizing_resource = fields.Char(string="realizingResource", help="")
    realizing_service = fields.Char(string="realizingService", help="")
    related_party = fields.Char(string="relatedParty", help="")
    status = fields.Char(string="status", help="Is the lifecycle status of the product.")

    def _get_tmf_api_path(self):
        return "/productManagement/v4/Product"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Product",
            "description": self.description,
            "isBundle": self.is_bundle,
            "isCustomerVisible": self.is_customer_visible,
            "name": self.name,
            "orderDate": self.order_date.isoformat() if self.order_date else None,
            "productSerialNumber": self.product_serial_number,
            "randomAtt": self.random_att,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "terminationDate": self.termination_date.isoformat() if self.termination_date else None,
            "agreement": self.agreement,
            "billingAccount": self.billing_account,
            "place": self.place,
            "product": self.product,
            "productCharacteristic": self.product_characteristic,
            "productOffering": self.product_offering,
            "productOrderItem": self.product_order_item,
            "productPrice": self.product_price,
            "productRelationship": self.product_relationship,
            "productSpecification": self.product_specification,
            "productTerm": self.product_term,
            "realizingResource": self.realizing_resource,
            "realizingService": self.realizing_service,
            "relatedParty": self.related_party,
            "status": self.status,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('product', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('product', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='product',
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
