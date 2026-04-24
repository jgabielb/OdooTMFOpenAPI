{
    "name": "TMF Sales Dashboard",
    "summary": "Customer portfolio view for salespersons: accounts, services, orders",
    "description": """
        Adds a 'Customer Portfolio' tab to the partner form showing:
        - TMF666 Accounts (billing, party, financial)
        - TMF638 Active Services
        - TMF622 Product Orders (sale.order)
        - TMF699 Sales Leads
        Gives salespersons a single view of everything a customer has.
    """,
    "author": "Joao Nascimento",
    "category": "TMF",
    "version": "0.1",
    "depends": [
        "tmf_party",
        "tmf_account",
        "tmf_service_inventory",
        "tmf_product_ordering",
        "tmf_sales",
        "sale_management",
    ],
    "data": [
        "views/res_partner_portfolio_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
