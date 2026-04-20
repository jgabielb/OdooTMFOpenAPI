"""Scenario 8: Multi-Service Customer (Integration)

Single customer with multiple services, accounts, and interactions.
End-to-end validation of full TAM coverage.
"""
import pytest
from helpers.assertions import *


class TestMultiServiceCustomer:

    def test_setup_customer(self, tmf):
        """Create the multi-service customer."""
        data, _ = tmf.create_party("Frank", "Garcia", contactMedium=[
            {"mediumType": "email", "characteristic": {"emailAddress": "frank@test.com"}},
            {"mediumType": "phone", "characteristic": {"phoneNumber": "+1555123456"}},
        ])
        self.__class__.party_id = data["id"]

    def test_create_three_accounts(self, tmf):
        """Create Personal, Business, and Family accounts."""
        ids = []
        for name in ["Personal", "Business", "Family"]:
            data, _ = tmf.create_billing_account(f"{name} Account", self.party_id)
            ids.append(data["id"])
        self.__class__.account_ids = ids
        assert len(ids) == 3

    def test_create_three_offerings(self, tmf):
        """Create Mobile, Internet, and TV offerings."""
        ids = []
        for name, price in [("Mobile 5G", 39.99), ("Fiber Internet", 59.99), ("TV Premium", 19.99)]:
            data, _ = tmf.create_product_offering(name, price=price)
            ids.append(data["id"])
        self.__class__.offering_ids = ids

    def test_create_three_orders(self, tmf):
        """Create one order per offering."""
        ids = []
        for offering_id in self.offering_ids:
            data, _ = tmf.create_product_order(self.party_id, offering_id)
            ids.append(data["id"])
        self.__class__.order_ids = ids
        assert len(ids) == 3

    def test_create_service_activations(self, tmf):
        """Activate services for each order."""
        ids = []
        for i, name in enumerate(["Mobile", "Internet", "TV"]):
            data, _ = tmf.create("service_activation", "service", {
                "serviceSpecification": {"id": f"spec-{name.lower()}"},
                "state": "active",
                "name": f"{name} Service for Frank",
            })
            ids.append(data["id"])
        self.__class__.service_ids = ids
        assert len(ids) == 3

    def test_create_usage_records(self, tmf):
        """Create usage records for each service."""
        for svc_id in self.service_ids:
            tmf.create("usage", "usage", {
                "name": f"Usage for {svc_id}",
                "usageDate": "2026-04-17T00:00:00Z",
                "usageType": "data",
                "relatedParty": [{"id": self.party_id}],
            })

    def test_send_communication(self, tmf):
        """Send bill notification."""
        data, _ = tmf.create("communication", "communicationMessage", {
            "content": "Your monthly bill is ready",
            "messageType": "email",
            "sender": {"id": "system", "name": "TelcoCo"},
            "receiver": [{"id": self.party_id, "name": "Frank Garcia"}],
        })
        assert_tmf_resource(data)

    def test_create_interaction(self, tmf):
        """Log customer interaction."""
        data, _ = tmf.create("party_interaction", "partyInteraction", {
            "@type": "PartyInteraction",
            "description": "Customer called about bill dispute",
            "direction": "inbound",
            "reason": "Bill dispute",
            "relatedChannel": [{"id": "phone", "name": "Phone"}],
            "interactionDate": {"startDateTime": "2026-04-17T09:00:00Z"},
            "relatedParty": [{"id": self.party_id}],
        })
        assert_tmf_resource(data)

    def test_verify_party_exists(self, tmf):
        """GET party shows all details."""
        data, _ = tmf.get("party", "individual", self.party_id)
        assert_tmf_resource(data, "Individual")
        assert_field_value(data, "givenName", "Frank")

    def test_verify_three_accounts(self, tmf):
        """All 3 accounts exist and are linked to the party."""
        for aid in self.account_ids:
            data, _ = tmf.get("account", "billingAccount", aid)
            related = data.get("relatedParty", [])
            party_refs = [p for p in related if p.get("id") == self.party_id]
            assert len(party_refs) >= 1, (
                f"Account {aid} missing relatedParty with id={self.party_id}, got {related}"
            )

    def test_verify_three_orders(self, tmf):
        """All 3 orders exist."""
        for oid in self.order_ids:
            data, _ = tmf.get("ordering", "productOrder", oid)
            assert_tmf_resource(data)

    def test_verify_services_active(self, tmf):
        """All 3 services are active."""
        for sid in self.service_ids:
            data, _ = tmf.get("service_activation", "service", sid)
            assert_field_value(data, "state", "active")
            assert_field_present(data, "serviceDate")

    def test_make_payments(self, tmf):
        """Pay each account."""
        for i, acct_id in enumerate(self.account_ids):
            tmf.create_payment(
                [39.99, 59.99, 19.99][i],
                acct_id,
                description=f"Payment {i+1}",
            )

    def test_create_trouble_ticket(self, tmf):
        """Create a ticket for one service issue."""
        data, _ = tmf.create_trouble_ticket(
            "Internet speed below SLA threshold",
            party_id=self.party_id,
            severity="Medium",
            ticketType="Complaint",
        )
        ticket_id = assert_tmf_resource(data)
        self.__class__.ticket_id = ticket_id

    def test_resolve_ticket(self, tmf):
        """Resolve the ticket."""
        data, _ = tmf.patch("trouble_ticket", "troubleTicket", self.ticket_id,
                            {"status": "Resolved"})

    def test_cross_domain_summary(self, tmf):
        """Final validation: all domains touched and working."""
        # This test just verifies we got here without failures
        assert self.party_id
        assert len(self.account_ids) == 3
        assert len(self.order_ids) == 3
        assert len(self.service_ids) == 3
        assert self.ticket_id
        print(f"\n✓ Multi-service customer test passed")
        print(f"  Party: {self.party_id}")
        print(f"  Accounts: {len(self.account_ids)}")
        print(f"  Orders: {len(self.order_ids)}")
        print(f"  Services: {len(self.service_ids)}")
        print(f"  Ticket: {self.ticket_id}")
