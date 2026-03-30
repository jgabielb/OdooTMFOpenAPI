{
    "name": "TMF680 Recommendation Management",
    "version": "19.0.1.0.0",
    "summary": "TMF680 Recommendation Management API",
    "author": "Joao Gabriel",
    "category": "TMF",
    "license": "LGPL-3",
    "depends": [
        "tmf_base",
        "tmf_product",
        "tmf_party",
        "tmf_shopping_cart",
        "tmf_product_ordering",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/generated_views.xml",
    ],
    "installable": True,
    "application": False,
}
