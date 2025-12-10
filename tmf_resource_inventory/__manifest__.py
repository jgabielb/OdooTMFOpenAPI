{
    'name': "TMF Resource Inventory",
    'summary': "Implements TMF639 Resource Inventory API",
    'description': """
        Maps Odoo Stock Lots (Serial Numbers) to TMF Resources.
        Links Services (TMF638) to Physical Resources (TMF639).
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_service_inventory', 'stock'],
    'data': [
        'views/resource_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}