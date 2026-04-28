{
    'name': 'TMF645 Credit Management',
    'version': '19.0.1.0.0',
    'author': 'Joao Nascimento',
    'license': 'LGPL-3',
    'category': 'TMF Open API',
    'summary': 'TMF645 Credit Management API — credit rating check + credit-block flag on partners',
    'depends': ['tmf_base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/credit_check_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
}
