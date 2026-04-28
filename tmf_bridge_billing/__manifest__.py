{
    "name": "TMF Billing Bridge",
    "summary": "Auto-create invoices and TMF CustomerBills when services are activated",
    "description": """
        When a tmf.service transitions to 'active' state, this bridge:
        1. Creates an Odoo invoice (account.move) from the originating sale order
        2. Creates a tmf.customer.bill linked to the invoice and BillingAccount
        3. Links the bill to the customer's BillingAccount

        This completes the order-to-cash lifecycle:
        Sale Order -> Service Provisioning -> Service Active -> Invoice -> Bill
    """,
    "author": "Joao Nascimento",
    "category": "TMF",
    "version": "0.1",
    "depends": [
        "tmf_base",
        "tmf_account",
        "tmf_service_inventory",
        "tmf_customer_bill_management",
        "tmf_billing_management",
        "tmf_bridge_provisioning",
        "tmf_sales_dashboard",
        "tmf_product",
        "tmf_party_role",
        "tmf_usage",
        "tmf_process_flow",
        "sale_management",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/tmf_account_views.xml",
        "views/portfolio_billing_views.xml",
        "views/tmf_customer_bill_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
