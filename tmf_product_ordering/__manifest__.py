{
    'name': "TMF Product Ordering",
    'summary': "Implements TMF622 Product Ordering API",
    'description': """
        Enables external systems to place orders in Odoo.
        - Maps TMF ProductOrder to Odoo sale.order
        - Maps TMF ProductOrderItem to Odoo sale.order.line
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_party', 'tmf_product_catalog', 'sale_management'],
    'data': [
        # We might add views later, but for now it's API only
    ],
    'installable': True,
    'license': 'LGPL-3',
}