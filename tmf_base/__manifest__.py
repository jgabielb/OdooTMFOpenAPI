{
    'name': "TM Forum Base",
    'summary': "Base technical module for TMF Open API compliance",
    'description': """
        Contains the core logic for TMF API implementation:
        - TMF ID generation (UUID)
        - Common Mixins (Lifecycle, HREF)
        - Error handling utilities
    """,
    'author': "Joao Nascimento",
    'website': "https://www.odoo.com",
    'category': 'Technical',
    'version': '0.1',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/tmf_hub_subscription_views.xml',
        'views/tmf_api_key_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}