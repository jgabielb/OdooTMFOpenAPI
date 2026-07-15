{
    "name": "TMFC055 Wiring - ServiceTestManagement",
    "version": "1.0.0",
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        'tmf_service_test', 'tmf_customer', 'tmf_party_role',
        'tmf_service_catalog', 'tmf_service_inventory', 'tmf_resource_inventory',
        'tmf_process_flow',
    ],
    "data": ["security/ir.model.access.csv"],
    "installable": True,
}
