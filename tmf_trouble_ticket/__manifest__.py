{
    'name': 'TMF Trouble Ticketing',
    'summary': 'Implements TMF621 Trouble Ticket API',
    'description': '\n        Manage customer support tickets.\n        - Maps TMF TroubleTicket to tmf.trouble.ticket\n        - Links tickets to Related Parties (Customers) and Related Entities (Services/Resources)\n    ',
    'author': 'Joao Gabriel',
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_party', 'tmf_service_inventory', 'tmf_product_catalog'],
    'data': ['security/ir.model.access.csv', 'views/generated_views.xml'],
    'installable': True,
    'license': 'LGPL-3',
}
