{
    "name": "TMFC038 Wiring - ResourcePerformanceManagement",
    "version": "1.0.0",
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        'tmf_performance_management', 'tmf_customer', 'tmf_party_role',
        'tmf_resource_inventory', 'tmf_resource_catalog',
        'tmf_geographic_address', 'tmf_process_flow',
    ],
    "data": ["security/ir.model.access.csv"],
    "installable": True,
}
