{
    'name': "TMF Product Catalog",
    'summary': "Implements TMF620 Product Catalog API",
    'description': """
        Separates Product Specifications (Technical) from Product Offerings (Commercial).
        - New Model: Product Specification
        - Extension: Product Template (as Product Offering)
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'product', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_specification_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}