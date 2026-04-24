{
    "name": "TMFC043 Wiring - FaultManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF621 TroubleTicket / TMF656 ServiceProblem / "
        "TMF642 Alarm refs (TMF632 Party, TMF638 Service, TMF639 Resource) with "
        "listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_trouble_ticket",
        "tmf_service_problem",
        "tmf_alarm",
        "tmf_customer",
        "tmf_party_role",
        "tmf_service_inventory",
        "tmf_resource_inventory",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
