{
    "name": "TMF Provisioning Bridge",
    "summary": "Auto-create TMF638 services when a sale order is confirmed",
    "description": """
        When a salesperson confirms a sale.order (draft -> sale), this bridge:
        1. Reads each order line's product -> productSpecification -> serviceSpecification
        2. Creates tmf.service records in 'feasabilityChecked' state
        3. Links services to the order line and customer
        4. Optionally allocates tmf.resource from stock if resourceSpecification is defined

        The provisioning lifecycle follows TMF standard:
        feasabilityChecked -> designed -> reserved -> inactive -> active

        External OSS/provisioning systems can advance the service state via TMF638 API.
    """,
    "author": "Joao Gabriel",
    "category": "TMF",
    "version": "0.1",
    "depends": [
        "tmf_base",
        "tmf_product_catalog",
        "tmf_product_ordering",
        "tmf_service_inventory",
        "tmf_account",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
