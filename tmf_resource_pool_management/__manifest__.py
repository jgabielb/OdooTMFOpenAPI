{
    'name': 'TMF685 Resource Pool Management',
    'version': '19.0.1.0.0',
    'author': 'Joao Nascimento',
    'summary': 'TMF685 Resource Pool Management API (CTK-oriented)',
    'category': 'TMF Open API',
    'depends': ['tmf_base', 'product', 'stock', 'tmf_product_catalog'],
    'data': ['security/ir.model.access.csv', 'views/capacity_specification_views.xml', 'views/resource_pool_spec_views.xml', 'views/resource_pool_views.xml', 'views/push_extract_availability_views.xml', 'views/menu.xml'],
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}
