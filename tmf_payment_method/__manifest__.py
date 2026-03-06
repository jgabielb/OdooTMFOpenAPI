{
    'name': 'TMF670 Payment Method Management',
    'version': '19.0.1.0.0',
    'category': 'TM Forum / ODA',
    'summary': 'TMF670 Payment Method API v4.0.0 implementation',
    'description': 'Implements TMF670 Payment Method API v4.0.0 (CRUD + Hub + Notifications).',
    'author': 'Your Team',
    'depends': ['base', 'tmf_base', 'account', 'tmf_product_catalog'],
    'data': ['security/ir.model.access.csv', 'views/payment_method_views.xml'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
