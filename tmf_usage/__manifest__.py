{
    'name': "TMF Usage (TMF635)",
    'summary': "TMF635 Usage Management API v4.0.0 - Odoo implementation",
    'description': "Implements Usage and UsageSpecification resources with CRUD + fields/filter/pagination and Hub notifications.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.2',
    'depends': ['tmf_base', 'tmf_product_catalog'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
