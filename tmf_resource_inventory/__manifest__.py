{
    'name': 'TMF Resource Inventory',
    'summary': 'Implements TMF639 Resource Inventory API',
    'description': '\n        Maps Odoo Stock Lots (Serial Numbers) to TMF Resources.\n        Links Services (TMF638) to Physical Resources (TMF639).\n    ',
    'author': 'Joao Nascimento',
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_service_inventory', 'stock', 'tmf_product_catalog'],
    'data': ['views/resource_views.xml'],
    'installable': True,
    'license': 'LGPL-3',
}
