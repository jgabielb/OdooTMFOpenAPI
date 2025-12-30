{
    'name': "TMF Permission",
    'summary': "Auto-generated implementation of User Roles And Permissions",
    'description': "Implements Permission API with Hub Notifications.",
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