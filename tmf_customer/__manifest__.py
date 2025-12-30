{
    'name': "TMF Customer",
    'summary': "Auto-generated implementation of Customer Management",
    'description': "Implements Customer API with Hub Notifications.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog'],
    'data': [
        'security/ir.model.access.csv',
        'views/tmf_customer_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}