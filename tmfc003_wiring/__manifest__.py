{
    "name": "TMFC003 Wiring - ProductOrderDeliveryOrchestrationAndManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires product orders (TMF622) to service orders (TMF641) "
        "and resource orders (TMF652), implements 3-layer state propagation, TMF701 "
        "process/task-flow provisioning per delivery, and listener routes for "
        "TMF641/TMF652 subscribed events."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_product_ordering",    # sale.order + TMF622 ProductOrder
        "tmf_service_order",       # tmf.service.order (TMF641)
        "tmf_resource_order",      # tmf.resource.order (TMF652)
        "tmf_product_inventory",   # tmf.product (TMF637)
        "tmf_service_inventory",   # tmf.service (TMF638) — backward-compat dependency
        "tmf_resource_inventory",  # stock.lot-based resource (TMF639)
        "tmf_process_flow",        # tmf.process.flow / tmf.task.flow (TMF701)
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
