{
    'name': "TMFC031 Cross-API Wiring",
    'summary': "Wires CustomerBill/AppliedBillingRate to TMF dependent APIs (TMFC031)",
    'description': """
        Resolves cross-API references for CustomerBill (tmf.customer.bill) and
        AppliedCustomerBillingRate (tmf.applied.customer.billing.rate) per TMFC031:
        - TMF666 billingAccount -> tmf.billing.account
        - TMF637 product -> tmf.product
        - TMF632 relatedParty -> res.partner
        - TMF635 usage -> tmf.usage
        - TMF669 partyRole -> tmf.party.role
        - TMF701 processFlow -> tmf.process.flow
    """,
    'author': "Joao Nascimento",
    'category': 'TMF',
    'version': '0.1',
    'depends': [
        'tmf_customer_bill_management',
        'tmf_billing_management',
        'tmf_product_inventory',
        'tmf_usage',
        'tmf_party_role',
        'tmf_process_flow',
    ],
    'data': [
        'views/wiring_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
