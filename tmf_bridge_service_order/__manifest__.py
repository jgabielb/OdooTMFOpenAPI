# -*- coding: utf-8 -*-
{
    "name": "Bridge: Odoo Sale Order ↔ TMF Service Order",
    "version": "19.0.1.0.0",
    "author": "Joao Gabriel",
    "category": "TMF/Bridge",
    "summary": "Bridge: Odoo Sale Order ↔ TMF Service Order",
    "depends": ["sale", "tmf_service_order"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
