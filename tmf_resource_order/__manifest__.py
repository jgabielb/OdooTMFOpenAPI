{
    'name': "TMF ResourceOrder",
    'summary': "Auto-generated implementation of Resource Ordering",
    'description': "Implements ResourceOrder API with Hub Notifications.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog', 'project', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
