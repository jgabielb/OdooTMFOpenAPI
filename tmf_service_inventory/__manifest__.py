{
    'name': "TMF Service Inventory",
    'summary': "Implements TMF638 Service Inventory API",
    'description': """
        Tracks active services (Installed Base).
        - New Model: tmf.service
        - Automates service creation when Sales Order is confirmed.
    """,
    'author': "Joao Nascimento",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_ordering', 'tmf_product_catalog', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/tmf_service_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
