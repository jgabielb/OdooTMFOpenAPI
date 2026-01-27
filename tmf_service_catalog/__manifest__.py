{
    'name': "TMF ServiceCatalog",
    'summary': "Auto-generated implementation of Service Catalog Management",
    'description': "Implements ServiceCatalog API with Hub Notifications.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
        'views/service_specification_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}