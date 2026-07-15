{
    "name": "TMFC007 Wiring - ServiceOrderManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF641 ServiceOrder to hub subscriptions "
        "and TMF701 process/task flows, adds state-change event coverage, "
        "and exposes listener scaffolding for TMF652/TMF645/TMF681/TMF697."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_service_order",      # tmf.service.order (TMF641)
        "tmf_service_inventory",  # tmf.service (TMF638)
        "tmf_resource_order",     # tmf.resource.order (TMF652)
        "tmf_process_flow",       # tmf.process.flow / tmf.task.flow (TMF701)
        "tmf_party_role",         # tmf.party.role (TMF669)
        "tmf_service_qualification",     # tmf.service.qualification (TMF645)
        "tmf_communication_message",     # tmf.communication.message (TMF681)
        "tmf_work_management",    # tmf.work / TMF697 WorkOrder representation
        "tmf_appointment",        # tmf.appointment (TMF646)
        "tmf_service_test",       # tmf.service.test (TMF653)
        "tmf_service_activation_configuration",  # tmf640.monitor (TMF640)
        "tmf_geographic_address",   # TMF673
        "tmf_geographic_site",      # TMF674
        "tmf_geographic_location",  # TMF675
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

