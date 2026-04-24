{
    'name': "TMF664 Resource Function Activation",
    'summary': "TMF664 Resource Function Activation and Configuration API",
    'description': "Implements TMF664 Resource Function Activation and Configuration API with hub notifications.",
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
