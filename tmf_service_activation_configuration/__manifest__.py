{
    'name': 'TMF640 Service Activation & Configuration',
    'summary': 'TMF640 v4 Service Activation and Configuration API implementation',
    'version': '0.1',
    'category': 'TMF',
    'author': 'Joao Gabriel',
    'depends': ['tmf_base', 'project', 'tmf_service_inventory', 'tmf_event', 'tmf_product_catalog'],
    'data': ['security/ir.model.access.csv', 'views/tmf640_service_views.xml', 'views/tmf640_monitor_views.xml', 'views/tmf640_hub_views.xml', 'views/tmf640_menu.xml'],
    'installable': True,
    'license': 'LGPL-3',
}
