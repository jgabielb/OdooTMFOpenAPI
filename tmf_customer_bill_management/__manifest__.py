{
    'name': 'TMF678 Customer Bill Management',
    'version': '19.0.1.0.0',
    'author': 'Joao Nascimento',
    'category': 'TMF',
    'summary': 'TMF678 CustomerBill API (Conformance v5) - CustomerBill, OnDemand, BillCycle, AppliedCustomerBillingRate',
    'depends': ['base', 'contacts', 'account', 'tmf_base', 'tmf_product_catalog'],
    'data': ['security/ir.model.access.csv', 'views/customer_bill_views.xml'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
