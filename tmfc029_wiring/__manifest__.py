{
    "name": "TMFC029 Wiring - PaymentManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car for PaymentManagement. Wires TMF676 Payment to "
        "BillingAccount (TMF666), CustomerBill (TMF678) and Party "
        "(TMF632), and exposes listener endpoints for those subscribed "
        "events without altering CTK-facing payment APIs."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_payment",
        "tmf_payment_method",
        "tmf_transfer_balance",
        "tmf_billing_management",
        "tmf_customer_bill_management",
        "tmf_customer",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
