{
    "name": "TMF711 Shipment Management",
    "summary": "TMF711 Shipment Management API",
    "description": "Implements TMF711 Shipment Management API with hub notifications.",
    "author": "Joao Gabriel",
    "category": "TMF",
    "version": "0.1",
    "depends": ["tmf_base", "tmf_product_catalog", "stock", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/generated_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
