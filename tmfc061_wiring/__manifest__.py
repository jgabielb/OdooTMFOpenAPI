{
    "name": "TMFC061 Wiring - WorkOrderManagement",
    "version": "1.0.0",
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        'tmf_work_management', 'tmf_customer', 'tmf_party_role',
        'tmf_work_qualification', 'tmf_appointment', 'tmf_process_flow',
        'tmf_event',
    ],
    "data": ["security/ir.model.access.csv"],
    "installable": True,
}
