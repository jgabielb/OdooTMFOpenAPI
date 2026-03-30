# -*- coding: utf-8 -*-
{
    "name": "TMF672 User Role Permission Management",
    "version": "19.0.1.0.0",
    "category": "TMF Open API",
    "summary": "Implements TMF672 v4 Permission and UserRole resources",
    "author": "Joao Gabriel",
    "depends": ["tmf_base"],
    "data": [
        "security/ir.model.access.csv",
        "views/permission_views.xml",
        "views/user_role_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
