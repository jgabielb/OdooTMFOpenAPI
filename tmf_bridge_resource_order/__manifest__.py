# -*- coding: utf-8 -*-
{
    "name": "Bridge: Odoo Purchase Order ↔ TMF Resource Order",
    "version": "17.0.1.0.0",
    "category": "TMF/Bridge",
    "summary": "Bridge: Odoo Purchase Order ↔ TMF Resource Order",
    "depends": ["purchase", "tmf_resource_order"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
