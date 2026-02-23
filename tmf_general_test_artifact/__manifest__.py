{
    'name': "TMF710 General Test Artifact",
    'summary': "TMF710 General Test Artifact Management API",
    'description': "Implements TMF710 General Test Artifact Management API with Hub notifications.",
    'author': "Joao Gabriel",
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
