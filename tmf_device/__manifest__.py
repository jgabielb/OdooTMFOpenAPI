{
    'name': "TMF Device",
    'summary': "Auto-generated implementation of IoT Device Management",
    'description': "Implements Device API with Hub Notifications.",
    'author': "Joao Nascimento",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}