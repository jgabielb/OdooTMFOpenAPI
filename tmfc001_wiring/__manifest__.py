{
    'name': "TMFC001 Cross-API Wiring",
    'summary': "Wires ProductOffering/ProductSpecification to TMF dependent APIs (TMFC001)",
    'description': """
        Resolves cross-API references for ProductOffering (product.template) and
        ProductSpecification (tmf.product.specification) per TMFC001:
        - TMF632 relatedParty -> res.partner
        - TMF633 serviceSpecification -> tmf.service.specification
        - TMF634 resourceSpecification -> tmf.resource.specification
        - TMF651 agreement/agreementSpecification -> tmf.agreement(.specification)
        - TMF662 entitySpecification -> tmf.entity.specification
        - TMF669 partyRole -> tmf.party.role
        - TMF673/674/675 place -> geographic models
        Listener routes: /tmfc001/listener/* — hub facade: /tmfc001/hub
    """,
    'author': "Joao Nascimento",
    'category': 'TMF/ODA',
    'version': '0.2',
    'depends': [
        'tmf_product_catalog',
        'tmf_party_role',
        'tmf_service_catalog',
        'tmf_resource_catalog',
        'tmf_agreement',
        'tmf_entity_catalog',
        'tmf_geographic_address',
        'tmf_geographic_site',
        'tmf_geographic_location',
    ],
    'data': [
        'views/wiring_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
