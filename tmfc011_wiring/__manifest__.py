{
    "name": "TMFC011 Wiring - ResourceOrderManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF652 ResourceOrder refs (TMF632 Party, "
        "TMF669 PartyRole, TMF634 ResourceSpecification) onto "
        "tmf.resource.order, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_resource_order",
        "tmf_resource_catalog",
        "tmf_customer",
        "tmf_party_role",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
