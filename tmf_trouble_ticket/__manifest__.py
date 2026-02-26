{
    'name': "TMF Trouble Ticketing",
    'summary': "Implements TMF621 Trouble Ticket API",
    'description': """
        Manage customer support tickets.
        - Maps TMF TroubleTicket to tmf.trouble.ticket
        - Links tickets to Related Parties (Customers) and Related Entities (Services/Resources)
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_party', 'tmf_service_inventory'],
    'data': [
        'security/ir.model.access.csv',
        'views/generated_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
