{
    'name': "TMF ServiceQualification",
    'summary': "Auto-generated implementation of Service Qualification Management",
    'description': "Implements ServiceQualification API with Hub Notifications.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog', 'tmf_geographic_address', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
