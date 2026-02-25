# -*- coding: utf-8 -*-
{
    "name": "TMF678 Customer Bill Management (v5)",
    "version": "19.0.1.0.0",
    "category": "TMF",
    "summary": "TMF678 CustomerBill API (Conformance v5) - CustomerBill, OnDemand, BillCycle, AppliedCustomerBillingRate",
    "depends": [
        "base",
        "contacts",
        "account",
        "tmf_base",  # expects tmf_base.models.tmf_mixin + tmf_hub_subscription if you use events
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/customer_bill_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
