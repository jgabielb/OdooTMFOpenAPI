{
    'name': "TMF Billing Management",
    'summary': "Implements TMF666 Account & TMF678 Customer Bill",
    'description': """
        Maps Odoo Invoicing to TMF Standards.
        - TMF666: Billing Account (linked to res.partner)
        - TMF678: Customer Bill (linked to account.move)
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.2',
    'depends': ['tmf_base', 'account', 'tmf_party', 'tmf_product_catalog'],
    'data': [
        'security/ir.model.access.csv',
        'views/billing_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}