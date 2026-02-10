# -*- coding: utf-8 -*-
{
    "name": "TMF657 Service Quality Management v4",
    "summary": "TMF657 Service Quality Management API (ServiceLevelObjective, ServiceLevelSpecification, Hub)",
    "version": "19.0.1.0.0",
    "category": "TMF Open APIs",
    "author": "You",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/service_level_objective_views.xml",
        "views/service_level_specification_views.xml",
        'views/actions.xml',
        "views/hub_views.xml",
    ],
    "application": False,
    "installable": True,
}
