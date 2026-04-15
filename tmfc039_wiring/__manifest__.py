{
    "name": "TMFC039 Wiring - AgreementManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF651 Agreement refs (TMF632 Party, "
        "TMF669 PartyRole, TMF620 ProductOffering) onto tmf.agreement, "
        "with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_agreement",
        "tmf_customer",
        "tmf_party_role",
        "tmf_product_catalog",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
