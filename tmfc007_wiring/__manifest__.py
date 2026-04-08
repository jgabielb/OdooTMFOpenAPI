{
    "name": "TMFC007 Wiring - ServiceOrderManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF641 ServiceOrder to hub subscriptions "
        "and TMF701 process/task flows, adds state-change event coverage, "
        "and exposes listener scaffolding for TMF652/TMF645/TMF681/TMF697."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_service_order",      # tmf.service.order (TMF641)
        "tmf_service_inventory",  # tmf.service (TMF638)
        "tmf_resource_order",     # tmf.resource.order (TMF652)
        "tmf_process_flow",       # tmf.process.flow / tmf.task.flow (TMF701)
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

