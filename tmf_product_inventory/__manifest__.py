{
    "name": "TMF637 Product Inventory Management",
    "summary": "Expose Product Inventory Management API (TMF637) over tmf.product",
    "description": "Implements TMF637 Product Inventory Management v5 endpoints for Product CRUD.",
    "author": "Joao Nascimento",
    "category": "TMF",
    "version": "0.1",
    "depends": [
        "tmf_base",
        "tmf_product",
        "tmf_product_catalog",
        "tmf_party",
        "tmf_geographic_address",
        # si ya tienes estos módulos y quieres enlazar realizingService/realizingResource:
        # "tmf_service_inventory",
        # "tmf_resource_inventory",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "license": "LGPL-3",
}
