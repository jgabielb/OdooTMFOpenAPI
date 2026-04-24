# -*- coding: utf-8 -*-
{
    "name": "TMF648 Quote Management",
    "summary": "TMF648 Quote Management API v4 implementation (Quote, Hub, Notifications skeleton)",
    "description": "Implements TMF648 Quote Management API v4 endpoints in Odoo.",
    "author": "Joao Nascimento",
    "category": "TMF",
    "version": "0.1",
    "depends": [
        "tmf_base",
        "crm",
        "sale_management",
        "tmf_party",                  # relatedParty
        "tmf_billing_management",     # billingAccount
        "tmf_agreement",              # agreement
        "tmf_product_catalog",        # productOffering/productSpecification refs
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/tmf_quote_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
