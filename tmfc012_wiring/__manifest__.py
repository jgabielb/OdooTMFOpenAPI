{
    "name": "TMFC012 Wiring - ResourceInventory",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF639 ResourceInventory refs onto "
        "stock.lot: TMF634 ResourceSpecification, TMF632 Party, "
        "TMF673/674/675 Geographic Address/Site/Location."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_resource_inventory",
        "tmf_resource_catalog",
        "tmf_customer",
        "tmf_party_role",
        "tmf_geographic_address",
        "tmf_geographic_site",
        "tmf_geographic_location",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
