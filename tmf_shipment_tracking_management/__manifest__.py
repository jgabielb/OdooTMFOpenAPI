{
    "name": "TMF684 Shipment Tracking Management",
    "summary": "TMF684 Shipment Tracking Management API",
    "description": "Implements TMF684 Shipment Tracking Management API with Odoo stock picking wiring.",
    "author": "Joao Gabriel",
    "category": "TMF",
    "version": "0.1",
    "depends": ["tmf_base", "stock", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/generated_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}

