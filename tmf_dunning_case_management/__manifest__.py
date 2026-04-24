{
    'name': 'TMF728 Dunning Case Management',
    'summary': 'TMF728 Dunning Case Management API',
    'description': 'Implements TMF728 Dunning Case Management API with DunningScenario, DunningRule and DunningCase resources.',
    'author': 'Joao Nascimento',
    'category': 'TMF',
    'version': '0.1',
    'depends': ['tmf_base', 'tmf_billing_management', 'account', 'contacts', 'tmf_product_catalog'],
    'data': ['security/ir.model.access.csv', 'views/generated_views.xml'],
    'installable': True,
    'license': 'LGPL-3',
}
