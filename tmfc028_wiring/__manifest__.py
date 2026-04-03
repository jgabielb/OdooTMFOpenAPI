{
    "name": "TMFC028 Party Management Wiring",
    "summary": "Side-car wiring for Party (TMF632) into Digital Identity, Privacy Agreements, and Party Interactions.",
    "version": "0.1",
    "author": "Joao Gabriel",
    "category": "TMF",
    "license": "LGPL-3",
    "depends": [
        "tmf_party",  # TMF632 core (res.partner TMF view)
        "tmf_digital_identity_management",  # TMF720
        "tmf_party_privacy_agreement",
        "tmf_party_interaction",
    ],
    "data": [],
    "installable": True,
}

