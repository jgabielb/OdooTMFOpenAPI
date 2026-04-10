{
    "name": "TMFC006 Wiring - ServiceCatalogManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires Service Catalog (TMF633) and Service Quality "
        "(TMF657) dependencies for TMFC006, adds foundational reference "
        "resolution for TMF634/TMF632/TMF669/TMF662, and exposes listener "
        "scaffolding for TMF634/TMF662 events plus optional TMF701 linkage."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_service_catalog",          # TMF633 ServiceCatalog / ServiceSpecification
        "tmf_service_quality_management",  # TMF657 serviceLevel* resources
        "tmf_resource_catalog",         # TMF634 ResourceSpecification
        "tmf_entity_catalog",           # TMF662 Entity/AssociationSpecification
        "tmf_customer",                 # TMF632 Party/Customer baseline
        "tmf_party_role",               # TMF669 PartyRole
        "tmf_process_flow",             # TMF701 shared process/task flows
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
