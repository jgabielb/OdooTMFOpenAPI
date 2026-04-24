{
    'name': "TMF Party Management",
    'summary': "Implements TMF632 Party Management API",
    'description': """
        Maps Odoo res.partner to TMF Individual and Organization.
        - Extends res.partner with TMF Mixin
        - Exposes API endpoints for Party
    """,
    'author': "Joao Nascimento",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
        'views/res_partner_tmf_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}