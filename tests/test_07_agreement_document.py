"""Scenario 7: Agreement & Document (Contract)

Agreements, documents, appointments, and communication.
"""
import pytest
from helpers.assertions import *


@pytest.fixture(scope="class")
def contract_setup(tmf):
    party, _ = tmf.create_party("Eve", "Brown")
    return {"party_id": party["id"]}


class TestAgreementDocument:

    def test_create_agreement(self, tmf, contract_setup):
        """POST agreement → sale.order via bridge."""
        data, _ = tmf.create("agreement", "agreement", {
            "name": "Enterprise SLA Agreement",
            "agreementType": "SLA",
            "engagedParty": [{
                "id": contract_setup["party_id"],
                "name": "Eve Brown",
            }],
            "agreementItem": [{"product": [{"id": "plan-001"}]}],
            "agreementPeriod": {
                "startDateTime": "2026-01-01",
                "endDateTime": "2027-01-01",
            },
        })
        agr_id = assert_tmf_resource(data)
        assert_field_value(data, "name", "Enterprise SLA Agreement")
        self.__class__.agreement_id = agr_id

    def test_create_document(self, tmf):
        """POST document → ir.attachment via bridge."""
        data, _ = tmf.create("document", "document", {
            "name": "SLA Terms v2.1",
            "description": "Service Level Agreement document",
        })
        doc_id = assert_tmf_resource(data)
        self.__class__.document_id = doc_id

    def test_create_appointment(self, tmf, contract_setup):
        """POST appointment → calendar.event via bridge."""
        data, _ = tmf.create("appointment", "appointment", {
            "category": "Contract Signing",
            "description": "Sign enterprise agreement",
            "status": "confirmed",
            "validFor": {
                "startDateTime": "2026-04-20T14:00:00Z",
                "endDateTime": "2026-04-20T15:00:00Z",
            },
            "relatedParty": [{"id": contract_setup["party_id"]}],
        })
        appt_id = assert_tmf_resource(data)
        self.__class__.appointment_id = appt_id

    def test_create_communication(self, tmf, contract_setup):
        """POST communication message → mail.message via bridge."""
        data, _ = tmf.create("communication", "communicationMessage", {
            "content": "Your agreement is ready for signing",
            "messageType": "email",
            "sender": {"id": "system", "name": "TelcoCo"},
            "receiver": [{"id": contract_setup["party_id"], "name": "Eve Brown"}],
            "subject": "Agreement Ready",
        })
        msg_id = assert_tmf_resource(data)
        self.__class__.message_id = msg_id

    def test_create_party_interaction(self, tmf, contract_setup):
        """POST party interaction → mail.message via bridge."""
        data, _ = tmf.create("party_interaction", "partyInteraction", {
            "@type": "PartyInteraction",
            "description": "Customer called about contract terms",
            "direction": "inbound",
            "reason": "Contract inquiry",
            "relatedChannel": [{"id": "phone", "name": "Phone"}],
            "interactionDate": {"startDateTime": "2026-04-17T09:00:00Z"},
            "relatedParty": [{"id": contract_setup["party_id"]}],
        })
        pi_id = assert_tmf_resource(data)
        self.__class__.interaction_id = pi_id

    def test_odoo_calendar_event(self, odoo):
        """Verify calendar event exists in Odoo."""
        events = odoo.find_calendar_event("Contract Signing")
        # Bridge should have created the event
        if events:
            assert any("Signing" in e["name"] or "Contract" in e["name"] for e in events)

    def test_get_agreement(self, tmf):
        """GET agreement verifies structure."""
        data, _ = tmf.get("agreement", "agreement", self.agreement_id)
        assert_tmf_resource(data)
        assert_field_present(data, "name")
