{
    'name': 'TMF657 Service Quality Management',
    'summary': 'TMF657 Service Quality Management API (ServiceLevelObjective, ServiceLevelSpecification, Hub)',
    'version': '19.0.1.0.0',
    'category': 'TMF Open APIs',
    'author': 'Joao Nascimento',
    'license': 'LGPL-3',
    'depends': ['base', 'tmf_product_catalog'],
    'data': [
        'security/ir.model.access.csv',
        'views/service_level_objective_views.xml',
        'views/service_level_specification_views.xml',
        'views/hub_views.xml',
        'views/actions.xml',
        'views/menu.xml',
    ],
    'application': False,
    'installable': True,
}
