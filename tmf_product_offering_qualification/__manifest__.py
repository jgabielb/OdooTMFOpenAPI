{
    'name': 'TMF Product Offering Qualification',
    'version': '1.0',
    'category': 'TMF/Sales',
    'summary': 'TMF679 Check Product Offering Qualification',
    'description': 'Implementation of TMF679 Check Product Offering Qualification API v5.0.0',
    'depends': [
        'base',
        'web',
        'tmf_base', # Critical: Required for tmf.model.mixin
        'tmf_product_catalog' # Optional: if you link to products
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}