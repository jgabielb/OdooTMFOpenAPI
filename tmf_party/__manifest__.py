{
    'name': "TMF Party Management",
    'summary': "Implements TMF632 Party Management API",
    'description': """
        Maps Odoo res.partner to TMF Individual and Organization.
        - Extends res.partner with TMF Mixin
        - Exposes API endpoints for Party
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'contacts'],
    'data': [],
    'installable': True,
    'license': 'LGPL-3',
}