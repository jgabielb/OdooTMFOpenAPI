{
    'name': "TMFC020 Cross-API Wiring",
    'summary': "Wires DigitalIdentity to TMF dependent APIs (TMFC020)",
    'description': """
        Resolves cross-API references for DigitalIdentity (tmf.digital.identity) per TMFC020:
        - TMF632 relatedParty / individualIdentified -> res.partner
        - TMF669 partyRoleIdentified / relatedParty -> tmf.party.role
        - TMF639 resourceIdentified -> stock.lot
    """,
    'author': "Joao Gabriel",
    'category': 'TMF',
    'version': '0.1',
    'depends': [
        'tmf_digital_identity_management',
        'tmf_party_role',
        'tmf_resource_inventory',
    ],
    'data': [
        'views/wiring_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
