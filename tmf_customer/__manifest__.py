{
    "name": "TMF Customer Management (TMF629)",
    "summary": "TMF629-style Customer API on top of Odoo res.partner",
    "version": "19.0.1.0.0",
    "author": "You",
    "website": "",
    "license": "LGPL-3",
    "category": "Telecom",
    "depends": [
        "base",
        "contacts",
        "tmf_base",  # uncomment if you already have it
        "tmf_party", # uncomment if you want tight integration
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/tmf_customer_views.xml",
    ],
    "installable": True,
    "application": False,
}
