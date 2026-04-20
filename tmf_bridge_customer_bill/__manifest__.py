# -*- coding: utf-8 -*-
{
    "name": "Bridge: Odoo Invoice ↔ TMF Customer Bill",
    "version": "19.0.1.0.0",
    "author": "Joao Gabriel",
    "category": "TMF/Bridge",
    "summary": "Bridge: Odoo Invoice ↔ TMF Customer Bill",
    "depends": ["account", "tmf_customer_bill_management"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
