{
    'name': "TMF ProductStockRelationship",
    'summary': "Auto-generated implementation of Stock Management",
    'description': "Implements ProductStockRelationship API with Hub Notifications.",
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