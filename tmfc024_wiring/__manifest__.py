{
    "name": "TMFC024 Wiring - BillingAccountManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF666 BillingAccount refs (TMF632 Party, "
        "TMF669 PartyRole, TMF678 CustomerBill, TMF676 PaymentMethod) onto "
        "tmf.billing.account, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "Joao Nascimento",
    "license": "LGPL-3",
    "depends": [
        "tmf_billing_management",
        "tmf_customer_bill_management",
        "tmf_payment_method",
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
