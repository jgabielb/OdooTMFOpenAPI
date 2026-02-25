{
    'name': "TMF687 Stock Management",
    'summary': "TMF687 Stock Management API v4",
    'description': "Implements TMF687 endpoints for ProductStock and ReserveProductStock.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
