{
    "name": "TMFC035 Wiring - PermissionsManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF672 Permission/UserRole refs "
        "(TMF632 Party, TMF669 PartyRole) onto tmf672.permission and "
        "tmf672.user.role, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_user_role_permission",
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
