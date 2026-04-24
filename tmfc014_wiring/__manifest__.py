{
    "name": "TMFC014 Wiring - LocationManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF673/TMF674/TMF675 location resources "
        "to TMF632 Party / TMF669 PartyRole, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_geographic_address",
        "tmf_geographic_site",
        "tmf_geographic_location",
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
