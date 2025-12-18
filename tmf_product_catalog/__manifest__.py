{
    'name': "TMF Product Catalog",
    'summary': "Implements TMF620 Product Catalog API",
    'description': """
        Separates Product Specifications (Technical) from Product Offerings (Commercial).
        - Product Specification (TMF620)
        - Product Template as Product Offering
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': [
        'tmf_base',
        'tmf_party',          # ✅ REQUIRED
        'product',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_specification_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
