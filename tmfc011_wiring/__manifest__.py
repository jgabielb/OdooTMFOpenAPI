{
    "name": "TMFC011 Wiring - ResourceOrderManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF652 ResourceOrder refs (TMF632 Party, "
        "TMF669 PartyRole, TMF634 ResourceSpecification) onto "
        "tmf.resource.order, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_resource_order",
        "tmf_resource_catalog",
        "tmf_customer",
        "tmf_party_role",
        "tmf_resource_inventory",      # stock.lot resources (TMF639)
        "tmf_resource_function",       # tmf.resource.function (TMF664)
        "tmf_resource_activation",     # tmf702.resource/monitor (TMF702)
        "tmf_resource_pool_management",  # tmf.resource.pool (TMF685)
        "tmf_work_management",         # tmf.work / WorkOrder (TMF697)
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
