{
    "name": "TMFC009 Wiring - ServiceQualificationManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF645 ServiceQualification refs "
        "(TMF632 Party, TMF669 PartyRole, TMF634 ServiceSpecification) "
        "onto tmf.service.qualification, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_service_qualification",
        "tmf_customer",
        "tmf_party_role",
        "tmf_service_catalog",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
