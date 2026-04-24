{
    "name": "TMFC008 Wiring - ServiceInventory",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires Service Inventory (TMF638) to its core "
        "dependencies (ServiceCatalog, ResourceInventory, Party/PartyRole, "
        "ServiceOrder) and provides listener scaffolding for TMFC008 "
        "subscribed events, plus optional TMF701 linkage."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_service_inventory",   # TMF638 service-inventory-management-api
        "tmf_service_catalog",     # TMF633 service-catalog-management-api
        "tmf_resource_inventory",  # TMF639 resource-inventory-management-api
        "tmf_resource_catalog",    # TMF634 ResourceSpecification via stock.lot.product_id
        "tmf_customer",            # TMF632 Party/Customer baseline
        "tmf_party_role",          # TMF669 PartyRole (no-op wiring for now)
        "tmf_service_order",       # TMF641 service-ordering-management-api
        "tmf_process_flow",        # TMF701 shared process/task flows
        "tmf_geographic_address",  # TMF673 GeographicAddress
        "tmf_geographic_site",     # TMF674 GeographicSite
        "tmf_geographic_location", # TMF675 GeographicLocation
        "tmf_permission",          # TMF672 Permission
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

