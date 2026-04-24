{
    "name": "TMF699 Sales Management",
    "summary": "TMF699 Sales Management API v4 implementation",
    "description": "Implements SalesLead, Hub subscription and listener endpoints for TMF699.",
    "author": "Joao Nascimento",
    "category": "TMF",
    "version": "0.1",
    "depends": [
        "tmf_base",
        "tmf_product_catalog",
        "tmf_quote_management",
        "tmf_agreement",
        "tmf_party_role",
        "tmf_process_flow",
        "crm",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/generated_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
