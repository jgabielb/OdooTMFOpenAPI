{
    'name': "TMF GeographicSite",
    'summary': "Auto-generated implementation of Geographic Site",
    'description': "Implements GeographicSite API with Hub Notifications.",
    'author': "Joao Nascimento",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog', 'tmf_geographic_address', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
