{
    "name": "TMFC040 Wiring - UsageManagement",
    "version": "1.0.0",
    "summary": (
        "ODA side-car that wires TMF635 Usage refs (TMF632 Party, "
        "TMF669 PartyRole, TMF678 CustomerBill/BillingAccount) onto tmf.usage, "
        "with listener + hub scaffolding."
    ),
    "category": "TMF/ODA",
    "author": "OdooBSS",
    "license": "LGPL-3",
    "depends": [
        "tmf_usage",
        "tmf_customer",
        "tmf_party_role",
        "tmf_billing_management",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
