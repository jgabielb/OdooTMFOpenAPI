{
    "name": "TMFC023 Party Interaction Management Wiring",
    "summary": "Side-car wiring for Party Interactions into the Party & Identity graph.",
    "version": "0.1",
    "author": "Joao Nascimento",
    "category": "TMF",
    "license": "LGPL-3",
    "depends": [
        "tmf_party_interaction",
        "tmf_party",
        "tmf_digital_identity_management",
        "tmf_party_privacy_agreement",
        "tmf_party_role",          # TMF669 partyRoleCreate subscription
        "tmf_document",            # tmf.document (TMF667)
        "tmf_communication_message",  # tmf.communication.message (TMF681)
        "tmf_entity_catalog",      # tmf.entity.specification (TMF662)
        "tmf_process_flow",        # TMF701 flow-event reconciliation
    ],
    "data": [],
    "installable": True,
}

