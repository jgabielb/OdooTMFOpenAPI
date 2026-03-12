{
    'name': "TMFC027 Cross-API Wiring",
    'summary': "Wires ProductOfferingQualification to TMF dependent APIs (TMFC027)",
    'description': """
        Resolves cross-API references for CheckProductOfferingQualification and
        QueryProductOfferingQualification per TMFC027:
        - TMF637 product -> tmf.product
        - TMF620 productOffering -> product.template
        - TMF622 productOrder -> sale.order
        - TMF632 relatedParty -> res.partner
        - TMF662 entityCatalog -> tmf.entity.specification
        - TMF666 billingAccount -> tmf.billing.account
        - TMF669 partyRole -> tmf.party.role
        - TMF673 geographicAddress -> tmf.geographic.address
        - TMF674 geographicSite -> tmf.geographic.site
        - TMF921 intent -> tmf.intent.management.resource
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.2',
    'depends': [
        'tmf_product_offering_qualification',
        'tmf_product_inventory',
        'tmf_product_ordering',
        'tmf_entity_catalog',
        'tmf_billing_management',
        'tmf_party_role',
        'tmf_geographic_address',
        'tmf_geographic_site',
        'tmf_intent_management',
    ],
    'data': [
        'views/wiring_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
