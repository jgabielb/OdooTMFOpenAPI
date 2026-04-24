{
    "name": "TMF700 Shipping Order Management",
    "summary": "TMF700 Shipping Order Management API v4.0 implementation",
    "description": "Implements ShippingOrder resource, hub subscription and listener endpoints for TMF700.",
    "author": "Joao Nascimento",
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
