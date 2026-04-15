{
    "name": "TMFC030 Wiring - BillGeneration",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF678 CustomerBill refs (TMF666 "
        "BillingAccount, TMF632 Party, TMF681 AppliedBillingRate) onto "
        "tmf.customer.bill, with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_customer_bill_management",
        "tmf_billing_management",
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
