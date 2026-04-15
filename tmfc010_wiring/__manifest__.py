{
    "name": "TMFC010 Wiring - ResourceCatalogManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF634 ResourceCatalog refs (TMF632 Party, "
        "TMF669 PartyRole, ResourceSpecification relationships) onto "
        "tmf.resource.specification, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
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
