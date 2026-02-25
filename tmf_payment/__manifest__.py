{
    'name': "TMF Payment",
    'summary': "Auto-generated implementation of Payment",
    'description': "Implements Payment API with Hub Notifications.",
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_product_catalog', 'contacts', 'account', 'tmf_payment_method'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
