{
    "name": "TMF Sales",
    "summary": "TMF699 Sales Management API v4 implementation",
    "description": "Implements SalesLead, Hub subscription and listener endpoints for TMF699.",
    "author": "Joao Gabriel",
    "category": "TMF",
    "version": "0.1",
    "depends": ["tmf_base", "tmf_product_catalog", "crm"],
    "data": [
        "security/ir.model.access.csv",
        "views/generated_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
